import os
import uuid
import logging
import asyncio
from datetime import datetime, timezone, timedelta

from fastapi import FastAPI, Form, HTTPException
from fastapi.responses import PlainTextResponse
from twilio.twiml.messaging_response import MessagingResponse

from langchain_core.messages import HumanMessage, AIMessage, BaseMessage
from agent.react_agent import agent, summarize_conversation, save_to_db_and_clear_cache
from storage.cache import hybrid_session_store

app = FastAPI()

# --- Serialization Helpers ---

def serialize_messages(messages: list[BaseMessage]) -> list[dict]:
    serialized = []
    for msg in messages:
        try:
            msg_dict = msg.dict() if hasattr(msg, "dict") else dict(msg)
            if isinstance(msg, HumanMessage):
                msg_dict["type"] = "human"
            elif isinstance(msg, AIMessage):
                msg_dict["type"] = "ai"
            else:
                msg_dict["type"] = "base"
            serialized.append(msg_dict)
        except Exception as e:
            logging.error(f"Error serializing message {msg}: {e}")
    return serialized

def deserialize_messages(messages_list: list[dict]) -> list[BaseMessage]:
    deserialized = []
    for msg_dict in messages_list:
        try:
            msg_type = msg_dict.get("type")
            if msg_type == "human":
                deserialized.append(HumanMessage(**msg_dict))
            elif msg_type == "ai":
                deserialized.append(AIMessage(**msg_dict))
            else:
                deserialized.append(BaseMessage(**msg_dict))
        except Exception as e:
            logging.error(f"Error deserializing message dict {msg_dict}: {e}")
    return deserialized

def serialize_datetime(dt: datetime | str | None) -> str | None:
    if dt is None:
        return None
    if isinstance(dt, str):
        return dt
    return dt.isoformat()

def deserialize_datetime(dt_str: str | datetime | None) -> datetime | None:
    if dt_str is None:
        return None
    if isinstance(dt_str, datetime):
        return dt_str
    try:
        return datetime.fromisoformat(dt_str)
    except Exception as e:
        logging.error(f"Error parsing datetime string {dt_str}: {e}")
        return None


# --- State Management Helpers ---

async def get_or_create_state(sender: str, username: str, mobile_number: str):
    state = await hybrid_session_store.get_state(sender)

    if not state:
        # New state
        state = {
            "messages": [],
            "mobile_number": mobile_number,
            "username": username,
            "conversation_summary": None,
            "last_db_save_time": serialize_datetime(datetime.now(timezone.utc)),
            "state_changed": False,
            "sentiment_label": None,
            "sentiment_score": None,
        }
    else:
        # Deserialize messages & datetime
        if "messages" in state:
            state["messages"] = deserialize_messages(state["messages"])
        state["last_db_save_time"] = deserialize_datetime(state.get("last_db_save_time"))
        # Update info if reconnected
        state["mobile_number"] = mobile_number
        state["username"] = username

    # Save immediately to keep data consistent (serialized)
    await hybrid_session_store.save_state(sender, {
        **state,
        "messages": serialize_messages(state["messages"]),
        "last_db_save_time": serialize_datetime(state["last_db_save_time"])
    })
    return state

async def save_state(sender: str, state: dict):
    # Serialize before saving
    state_to_save = {
        **state,
        "messages": serialize_messages(state.get("messages", [])),
        "last_db_save_time": serialize_datetime(state.get("last_db_save_time"))
    }
    await hybrid_session_store.save_state(sender, state_to_save)


# --- FastAPI WhatsApp Webhook ---

@app.post("/whatsapp")
async def whatsapp_webhook(
    From: str = Form(...),
    Body: str = Form(...),
    ProfileName: str = Form(None),
):
    sender = From
    username = ProfileName or "Unknown"
    mobile_number = sender.replace("whatsapp:", "")
    user_message = Body.strip()

    try:
        # 1) Load or create state
        state = await get_or_create_state(sender, username, mobile_number)

        # 2) Append user message
        state["messages"].append(HumanMessage(content=f"[User: {username} | Mobile: {mobile_number}] {user_message}"))
        state["state_changed"] = True

        # 3) Run agent
        config = {"configurable": {"thread_id": str(uuid.uuid4())},
                  "tools": [] }

        if hasattr(agent, "ainvoke"):
            result = await agent.ainvoke(state, config)
        else:
            result = await asyncio.to_thread(agent.invoke, state, config)

        ai_reply = result["messages"][-1].content
        state["messages"].append(AIMessage(content=ai_reply))
        state["state_changed"] = True

        # 4) Periodic DB save (every 12 hours)
        now = datetime.now(timezone.utc)
        last_save = state.get("last_db_save_time") or now
        if isinstance(last_save, str):
            last_save = deserialize_datetime(last_save)

        if state["state_changed"] and (now - last_save) > timedelta(hours=12):
            summary = await summarize_conversation(state["messages"])
            state["conversation_summary"] = summary

            await save_to_db_and_clear_cache(state)

            state["last_db_save_time"] = now
            state["state_changed"] = False
            logging.info(f"[Scheduled Save] Saved summary to DB for {mobile_number}")

            # Clear full state from Redis after save
            await hybrid_session_store.delete_state(sender)
        else:
            # Save updated state back to Redis
            await save_state(sender, state)

        # 5) Respond to WhatsApp
        resp = MessagingResponse()
        resp.message(ai_reply)
        return PlainTextResponse(str(resp), media_type="application/xml")

    except Exception as e:
        logging.error(f"Error in whatsapp_webhook: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal Server Error")
