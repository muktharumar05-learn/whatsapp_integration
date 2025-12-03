import logging
import os
import asyncio
from datetime import datetime
from typing import Annotated, Sequence, TypedDict, Optional

import yaml
from langchain_core.messages import (AIMessage, BaseMessage, HumanMessage, SystemMessage)
from langchain_groq import ChatGroq
from langgraph.graph import StateGraph
from langgraph.graph.message import add_messages

from storage.cache import checkpoint_saver
from storage.database import save_lead_to_db


# -----------------------
#   Lead State
# -----------------------
class LeadState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], add_messages]
    mobile_number: str
    username: str | None
    conversation_summary: str | None
    last_db_save_time: datetime
    state_changed: bool
    sentiment_label: Optional[str]
    sentiment_score: Optional[float]


# -----------------------
#  Async LLM Provider
# -----------------------
async def get_llm_async() -> ChatGroq:
    with open("config.yaml", "r") as file:
        config = yaml.safe_load(file)

    llm = ChatGroq(
        model=config["model"]["groq"]["model_name"],
        temperature=config["model"]["groq"]["temperature"],
        max_tokens=config["model"]["groq"]["max_tokens"],
        api_key=os.getenv(config["model"]["groq"]["api_key_env"]),
    )
    return llm


# -----------------------
#   PROMPTS
# -----------------------
with open("prompts/system_prompt.txt", "r", encoding="utf-8") as file:
    SYSTEM_PROMPT_TEMPLATE = file.read()

with open("prompts/summary_prompt.txt", "r", encoding="utf-8") as file:
    SUMMARY_PROMPT_TEMPLATE = file.read()


# -----------------------
#   Helpers
# -----------------------
async def summarize_conversation(messages: list[BaseMessage]) -> str:
    llm = await get_llm_async()

    conv_text = ""
    for msg in messages:
        role = "User" if isinstance(msg, HumanMessage) else "AI"
        conv_text += f"{role}: {msg.content}\n"

    prompt = SUMMARY_PROMPT_TEMPLATE.format(
        conversation=conv_text,
        mobile_number=messages[0].meta.get("mobile_number", "Unknown") if messages else "Unknown",
        username=messages[0].meta.get("username", "there") if messages else "there"
    )

    messages_for_summary = [SystemMessage(content=prompt)]

    if hasattr(llm, "ainvoke"):
        result = await llm.ainvoke(messages_for_summary)
    else:
        result = await asyncio.to_thread(llm.invoke, messages_for_summary)

    return result.content.strip()


async def extract_sentiment_from_summary(summary_text: str, llm: ChatGroq):
    prompt = """
Analyze the conversation summary and return ONLY a valid JSON string with keys:
{
  "sentiment_label": "Positive" | "Neutral" | "Negative",
  "sentiment_score": -1.0 to 1.0
}
Do NOT include any extra text or explanation.

Summary: 
""" + summary_text

    if hasattr(llm, "ainvoke"):
        result = await llm.ainvoke([HumanMessage(content=prompt)])
    else:
        result = await asyncio.to_thread(llm.invoke, [HumanMessage(content=prompt)])

    import json
    try:
        data = json.loads(result.content.strip())
        return data.get("sentiment_label", "Neutral"), float(data.get("sentiment_score", 0.0))
    except Exception as e:
        logging.error(f"Failed to parse sentiment JSON: {e}. Raw output: {result.content.strip()}")
        return "Neutral", 0.0


# -----------------------
#   react Agent Node (async)
# -----------------------
async def create_react_agent(state: LeadState):
    llm = await get_llm_async()

    messages = [SystemMessage(content=SYSTEM_PROMPT_TEMPLATE.format(username=state.get("username", "there")))] + list(state["messages"])

    if hasattr(llm, "ainvoke"):
        result = await llm.ainvoke(messages)
    else:
        result = await asyncio.to_thread(llm.invoke, messages)

    ai_msg = AIMessage(content=result.content)
    return {"messages": [ai_msg]}


# -----------------------
#  Human Review Node (async)
# -----------------------
async def human_response(state: LeadState):
    # LangGraph will pause here for human review; nothing to do
    return state


# -----------------------
# Build Graph
# -----------------------
workflow = StateGraph(LeadState)

workflow.add_node("react_agent", create_react_agent)
workflow.add_node("human_response", human_response)

workflow.set_entry_point("react_agent")
workflow.add_edge("human_response", "react_agent")
workflow.add_edge("react_agent", "human_response")

agent = workflow.compile(
    interrupt_before=["human_response"],
    checkpointer=checkpoint_saver,
)


# -----------------------
# Save to DB & Clear Cache (async)
# -----------------------
async def save_to_db_and_clear_cache(state: LeadState):
    llm = await get_llm_async()

    summary = await summarize_conversation(state["messages"])
    state["conversation_summary"] = summary

    label, score = await extract_sentiment_from_summary(summary, llm)
    state["sentiment_label"] = label
    state["sentiment_score"] = score

    await asyncio.to_thread(
        save_lead_to_db,
        state.get("mobile_number"),
        state.get("username"),
        summary,
        state.get("sentiment_label"),
        state.get("sentiment_score"),
    )
    logging.info(f"Saved summary + sentiment for {state.get('mobile_number')}")

    await asyncio.to_thread(checkpoint_saver.aclear_tuple, {"key": state["mobile_number"]})
    logging.info(f"Cleared cache for {state['mobile_number']}")