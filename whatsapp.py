from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel
from typing import Optional, Annotated, Sequence, TypedDict
from uuid import uuid4
from langchain_core.messages import SystemMessage, AIMessage, HumanMessage, BaseMessage
from langgraph.graph.message import add_messages
from lead_agent import agent  # Your existing agent

app = FastAPI()

# Conversation state model
class LeadState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], add_messages]

# Request and response schemas
class ChatRequest(BaseModel):
    session_id: Optional[str] = None
    user_message: str

class ChatResponse(BaseModel):
    session_id: str
    ai_reply: str

# In-memory conversation store
conversations: dict[str, LeadState] = {}

@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    session_id = req.session_id or str(uuid4())
    if session_id not in conversations:
        conversations[session_id] = {"messages": []}
    state = conversations[session_id]

    # Append user message
    state["messages"].append(HumanMessage(content=req.user_message))

    # Run agent
    result = agent.invoke(state)
    ai_reply = result["messages"][-1].content

    # Append AI response
    state["messages"].append(AIMessage(content=ai_reply))
    conversations[session_id] = state

    return ChatResponse(session_id=session_id, ai_reply=ai_reply)

@app.get("/chat", response_model=ChatResponse)
def get_last_ai_response(session_id: str = Query(...)):
    if session_id not in conversations or not conversations[session_id]["messages"]:
        raise HTTPException(status_code=404, detail="Session not found or no messages yet")

    messages = conversations[session_id]["messages"]
    for msg in reversed(messages):
        if isinstance(msg, AIMessage):
            return ChatResponse(session_id=session_id, ai_reply=msg.content)

    raise HTTPException(status_code=404, detail="No AI response found yet in this session")
