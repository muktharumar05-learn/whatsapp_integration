import logging
import os
import asyncio
from pyexpat.errors import messages
import traceback
from typing import Annotated, Sequence, TypedDict, Optional
import yaml
from langchain_core.messages import (AIMessage, BaseMessage, HumanMessage, SystemMessage)
from langchain_groq import ChatGroq
from langgraph.graph import StateGraph
from langgraph.graph.message import add_messages
from datetime import datetime, timedelta, timezone
from database.create_data import patch_lead_sentiment 
from client.twilio_client import send_whatsapp_message
from rag.retrieve import RagRetriever

# -----------------------
#   Lead State
# -----------------------
class LeadState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], add_messages]
    client_mobile_number: str
    user_mobile_number: str
    username: str | None
    conversation_summary: str | None
    sentiment_label: Optional[str]
    sentiment_score: Optional[float]
    last_active: Optional[datetime]
    insert_lead: Optional[bool]
    
# -----------------------
#  Global Session Manager
# -----------------------
ACTIVE_SESSIONS = {}  # key: user_mobile_number, value: LeadState object

# -----------------------
#  Async LLM Provider
# -----------------------
async def get_llm_async() -> ChatGroq:
    try:
        with open("config.yaml", "r") as file:
            config = yaml.safe_load(file)

        llm = ChatGroq(
            model=config["model"]["groq"]["model_name"],
            temperature=config["model"]["groq"]["temperature"],
            max_tokens=config["model"]["groq"]["max_tokens"],
            api_key=os.getenv(config["model"]["groq"]["api_key_env"]),
        )
        return llm
    except Exception as e:
        logging.error(f"Error loading LLM config or creating LLM instance: {e}")
        raise
    
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
    try:
        llm = await get_llm_async()

        conv_text = ""
        for msg in messages:
            role = "User" if isinstance(msg, HumanMessage) else "AI"
            content = getattr(msg, "content", "")
            conv_text += f"{role}: {content}\n"

        # Safely extract metadata
        if messages:
            msg0 = messages[0]
            metadata = {}
            if hasattr(msg0, "metadata") and isinstance(msg0.metadata, dict):
                metadata.update(msg0.metadata)
            if hasattr(msg0, "additional_kwargs") and isinstance(msg0.additional_kwargs, dict):
                metadata.update(msg0.additional_kwargs)
            user_mobile_number = metadata.get("user_mobile_number", "Unknown")
            username = metadata.get("username", "there")
        else:
            user_mobile_number = "Unknown"
            username = "there"

        prompt = SUMMARY_PROMPT_TEMPLATE.format(
            conversation=conv_text,
            user_mobile_number=user_mobile_number,
            username=username
        )

        messages_for_summary = [SystemMessage(content=prompt)]

        if hasattr(llm, "ainvoke"):
            result = await llm.ainvoke(messages_for_summary)
        else:
            result = await asyncio.to_thread(llm.invoke, messages_for_summary)

        content = getattr(result, "content", result) if result is not None else ""
        return str(content).strip()
    except Exception as e:
        logging.error(f"Error summarizing conversation: {e}")
        return ""

async def extract_sentiment_from_summary(summary_text: str, llm: ChatGroq):
    try:
        prompt = f"""
Analyze the sentiment of this car dealership lead summary.
NOTE: If the user shows interest in a vehicle, buying, or asking questions, mark as "Positive".

Summary: {summary_text}

Return ONLY a valid JSON string:
{{
  "sentiment_label": "Positive" | "Neutral" | "Negative",
  "sentiment_score": -1.0 to 1.0
}}

Do NOT include any extra text or explanation.

Summary: 
"""+ summary_text

        if hasattr(llm, "ainvoke"):
            result = await llm.ainvoke([HumanMessage(content=prompt)])
        else:
            result = await asyncio.to_thread(llm.invoke, [HumanMessage(content=prompt)])

        import json
        raw = getattr(result, "content", result)
        data = json.loads(str(raw).strip())
        return data.get("sentiment_label", "Neutral"), float(data.get("sentiment_score", 0.0))
    except Exception as e:
        logging.error(f"Failed to parse sentiment JSON or extract sentiment: {e}. Raw output: {raw if 'raw' in locals() else 'N/A'}")
        return "Neutral", 0.0

# -----------------------
#   react Agent Node (async)
# -----------------------
async def create_react_agent(state: LeadState):
    try:
        llm = await get_llm_async()
        user_messages = list(state["messages"])
        latest_user_message = None

        # Find the latest human message
        for msg in reversed(user_messages):
            if isinstance(msg, HumanMessage):
                latest_user_message = msg.content
                break

        retrieved_info = ""
        logging.info("Performing RAG retrieval...")
        logging.info("TYPE OF USER MESSAGE:", type(latest_user_message))
        logging.info("RAW VALUE:", repr(latest_user_message))
        rag_retriever = RagRetriever()
        retrieved_text = rag_retriever.query(
                                                query_text=str(latest_user_message), 
                                                customer=state.get("client_mobile_number")
                                            )
        retrieved_info = " ".join([doc["document"] for doc in retrieved_text])
        print("Customer:", state.get("client_mobile_number"))
        retrieved_info = "\n\nRetrieved info:\n" + retrieved_info
        logging.info(f"Retrieved info: {retrieved_info}")
        system_prompt = SYSTEM_PROMPT_TEMPLATE + retrieved_info
        retrieved_info = ""

        # Prepare messages with system prompt and conversation history
        messages = [SystemMessage(content=system_prompt)]

        # Add user messages after system and retrieved info
        summary = await summarize_conversation(user_messages)
        messages.extend(summary)
        if latest_user_message:
            messages.append(HumanMessage(content=latest_user_message))


        # Call LLM
        if hasattr(llm, "ainvoke"):
            result = await llm.ainvoke(input=messages)
        else:
            result = await asyncio.to_thread(llm.invoke, input=messages)

        # update last active time and reset save flag
        # 1. Update the Global Manager
        user_phone = state.get("user_mobile_number")
        if user_phone:
            ACTIVE_SESSIONS[user_phone] = state
        state["last_active"] = datetime.now(timezone.utc)
        state["insert_lead"] = False

        ai_content = getattr(result, "content", result)
        ai_msg = AIMessage(content=str(ai_content))
        return {"messages": [ai_msg]}

    except Exception as e:
        logging.error(traceback.format_exc())
        logging.error(f"Error in create_react_agent: {e}")
        return {"messages": [AIMessage(content='Sorry, an error occurred in processing your request.')]}


# -----------------------
#  Human Review Node (async)
# -----------------------
async def human_response(state: LeadState):
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
    interrupt_before=["human_response"]
)

# -----------------------
#   Save Task
# -----------------------
async def monitor_active_leads():
    """
    ONE loop that watches EVERYONE in ACTIVE_SESSIONS.
    """
    logging.info("🚀 Global lead monitor started.")
    while True:
        try:
            now = datetime.now(timezone.utc)
            # Create a list of keys to avoid 'dict changed size during iteration'
            for phone in list(ACTIVE_SESSIONS.keys()):
                state = ACTIVE_SESSIONS[phone]
                
                if state.get("insert_lead"): # Already patched
                    continue

                last_active = state.get("last_active")
                if not last_active: continue

                # 10 Minute Timeout (or 2 mins as per your recent snippet)
                if now - last_active > timedelta(minutes=2):
                    logging.info(f"⏰ Inactivity detected for {phone}. Patching...")
                    
                    summary = await summarize_conversation(state["messages"])
                    llm = await get_llm_async()
                    label, score = await extract_sentiment_from_summary(summary, llm)
                    logging.info(f"📝 Summary: {summary}")
                    logging.info(f"💡 Sentiment for {phone}: {label} ({score})")
                    
                    # 🔹 Execute the Patch
                    await patch_lead_sentiment(
                        phone_number=phone,
                        summary=summary,
                        sentiment_label=label,
                        sentiment_score=score
                    )
                    
                    state["insert_lead"] = True # Mark as done
                    logging.info(f"✅ Successfully patched {phone}")

            await asyncio.sleep(10) # Check all users every 10 seconds
        except Exception as e:
            logging.error(f"Monitor error: {e}")
            await asyncio.sleep(10)