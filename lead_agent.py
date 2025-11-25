from typing import Annotated, Sequence, TypedDict
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage, SystemMessage, AIMessage, HumanMessage
from langchain_groq import ChatGroq
from langgraph.graph import StateGraph, END
import yaml
from inputimeout import inputimeout, TimeoutOccurred

class LeadState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], add_messages]


# -----------------------
#  LLM Provider
# -----------------------
def get_llm() -> ChatGroq:
    with open("config.yaml", "r") as file:
        config = yaml.safe_load(file)

    return ChatGroq(
            model= config["model"]["groq"]["model_name"],
            temperature=config["model"]["groq"]["temperature"],
            max_tokens=config["model"]["groq"]["max_tokens"],
            api_key=config["model"]["groq"]["api_key_env"]
        )


# -----------------------
#   LLM Node
# -----------------------
SYSTEM_PROMPT = """You are a helpful AI Agent in getting leads for campaign.
Have a conversation to get more details to convert them into leads.
Make sure to ask relevant questions and be polite.
Once you have enough information, summarize the lead details clearly.
Respond to the user accordingly.

Here are some example questions to ask:
1. Thank you for taking interest in our ML course, could you please share from where you are and how you would like to have the course? Online or offline?
2. Thank you for reaching out to us! We are happy to partner with you for a business collaboration. Could you please provide more details about your business and the type of collaboration you have in mind?
3. We appreciate your interest in our services! To better assist you, could you please provide more information about your specific needs and requirements?

If for any reason, user asks you to stop, politely end the conversation.

If for any reason, you are unable to get lead information, politely gather the information again.

If you have enough information to summarize the lead, do so in a clear and concise manner.

If user says no for any question, politely ask for alternative information to gather lead details.

If user says "Hello" or "Hi", greet them politely and ask how you can assist them, don't ask for lead details right away or give any details about the course or service.
"""

SUMMARY_PROMPT = """You are a helpful assistant. Based on the conversation below, 
please summarize the lead details clearly and concisely:

{conversation}

Summary:
"""

def create_react_agent(state: LeadState):
    llm = get_llm()

    # Use fixed system prompt only
    messages = [SystemMessage(content=SYSTEM_PROMPT)] + list(state["messages"])

    result = llm.invoke(messages)

    return {"messages": [AIMessage(content=result.content)]}

def summarize_conversation(messages: list[BaseMessage]) -> str:
    llm = get_llm()

    # Format conversation as a simple text block
    convo_text = ""
    for msg in messages:
        role = "User" if isinstance(msg, HumanMessage) else "AI"
        convo_text += f"{role}: {msg.content}\n"

    prompt = SUMMARY_PROMPT.format(conversation=convo_text)

    # Use system message + prompt as one message to the LLM
    messages_for_summary = [SystemMessage(content=prompt)]

    result = llm.invoke(messages_for_summary)
    return result.content.strip()

# -----------------------
#  Human Review Node
# -----------------------
def human_response(state: LeadState):
    return state  # do nothing, but LangGraph pauses here


# -----------------------
# Build Graph
# -----------------------
workflow = StateGraph(LeadState)

workflow.add_node("react_agent", create_react_agent)
workflow.add_node("human_response", human_response)

workflow.set_entry_point("react_agent")
workflow.add_edge("human_response", "react_agent")
workflow.add_edge("react_agent", "human_response")

agent = workflow.compile(interrupt_before=["human_response"])


if __name__ == "__main__":
    # Initialize empty message history
    state = {"messages": []}

    while True:
        try:
            user_input = inputimeout(prompt="Hi,", timeout=1800).strip()
        except TimeoutOccurred:
            print("\nNo user input detected. Summarizing conversation...")

            summary = summarize_conversation(state["messages"])  # you define this function
            print("\nLead Summary:\n", summary)

            # TODO: Save summary to DB

            break
        if user_input.lower() in {"stop", "exit", "no more"}:
            print("Conversation ended by user.")
            break

        # Append user message to history
        state["messages"].append(HumanMessage(content=user_input))

        # Invoke agent with full conversation history
        result = agent.invoke(state)

        # Extract AI response
        ai_reply = result["messages"][-1].content
        print("\nAI:", ai_reply)

        # Append AI response to history for next turn
        state["messages"].append(AIMessage(content=ai_reply))
