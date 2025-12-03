import orjson
import logging
from typing import Optional, Dict, Any
import os
from dotenv import load_dotenv
import redis.asyncio as redis
from langgraph.checkpoint.redis import RedisSaver
from langchain_core.messages import HumanMessage, AIMessage, BaseMessage
from datetime import datetime

load_dotenv()
logging.basicConfig(level=logging.INFO)

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
SESSION_TTL_SECONDS = 60 * 60 * 24  # 24 hours

# Async Redis client for general use
redis_client = redis.from_url(REDIS_URL, decode_responses=False)

class AsyncRedisCheckpointSaver(RedisSaver):
    def __init__(self, redis_url: str, ttl: int = SESSION_TTL_SECONDS):
        super().__init__(redis_url)
        self.ttl = ttl
        # Override Redis client with async Redis client
        self.redis = redis.from_url(redis_url, decode_responses=False)

    async def aget_tuple(self, checkpoint_config: Dict[str, Any]) -> Optional[tuple]:
        key = checkpoint_config.get("key")
        if not key:
            return None
        data = await self.redis.get(key)
        if not data:
            return None
        try:
            decoded = orjson.loads(data)
        except Exception as e:
            logging.error(f"Error decoding checkpoint data for {key}: {e}")
            return None
        return (decoded, None)

    async def aset_tuple(self, checkpoint_config: Dict[str, Any], value: Any):
        key = checkpoint_config.get("key")
        if not key:
            return
        try:
            data = orjson.dumps(value)
            await self.redis.set(key, data, ex=self.ttl)
        except Exception as e:
            logging.error(f"Error saving checkpoint data for {key}: {e}")

    async def aclear_tuple(self, checkpoint_config: Dict[str, Any]):
        key = checkpoint_config.get("key")
        if not key:
            return
        try:
            await self.redis.delete(key)
        except Exception as e:
            logging.error(f"Error deleting checkpoint data for {key}: {e}")

    # Implement aput to conform with LangGraph expectations
    async def aput(self, checkpoint_config: Dict[str, Any], value: Any, *args, **kwargs):
        await self.aset_tuple(checkpoint_config, value)

    # Implement aput_writes to avoid NotImplementedError in LangGraph
    async def aput_writes(self, checkpoint_config: Dict[str, Any], writes: list, *args, **kwargs):
        """
        `writes` is expected to be a list of tuples or (key, value) pairs.
        For each write, call aput with the appropriate checkpoint_config.
        """
        for key, value in writes:
            config = dict(checkpoint_config)
            config["key"] = key
            await self.aput(config, value, *args, **kwargs)

checkpoint_saver = AsyncRedisCheckpointSaver(REDIS_URL, SESSION_TTL_SECONDS)

class HybridRedisSessionStore:
    def __init__(self):
        self.checkpoint_saver = checkpoint_saver
        self.redis_client = redis_client

    def _encode(self, data: Dict[str, Any]) -> bytes:
        try:
            return orjson.dumps(data)
        except Exception as e:
            logging.error(f"Error encoding data to JSON: {e}")
            return b"{}"

    def _decode(self, data: Optional[bytes]) -> Optional[Dict[str, Any]]:
        if data is None:
            return None
        try:
            return orjson.loads(data)
        except Exception as e:
            logging.error(f"Error decoding JSON data: {e}")
            return None

    # Serialize LangChain messages into dicts
    def serialize_messages(self, messages):
        serialized = []
        for msg in messages:
            if hasattr(msg, "dict"):
                serialized.append(msg.dict())
            else:
                serialized.append(msg)
        return serialized

    # Deserialize dicts back into LangChain message objects
    def deserialize_messages(self, messages_list):
        deserialized = []
        for msg_dict in messages_list:
            msg_type = msg_dict.get("type") or msg_dict.get("_type")
            if msg_type == "human":
                deserialized.append(HumanMessage(**msg_dict))
            elif msg_type == "ai":
                deserialized.append(AIMessage(**msg_dict))
            else:
                deserialized.append(BaseMessage(**msg_dict))
        return deserialized

    async def get_state(self, session_id: str) -> Optional[Dict[str, Any]]:
        checkpoint_state = None
        leadstate = {}

        try:
            result = await self.checkpoint_saver.aget_tuple({"key": session_id})
            if result:
                checkpoint_state = result[0]
                if isinstance(checkpoint_state, bytes):
                    checkpoint_state = self._decode(checkpoint_state)
                if checkpoint_state and "messages" in checkpoint_state:
                    checkpoint_state["messages"] = self.deserialize_messages(checkpoint_state["messages"])
            else:
                checkpoint_state = None
        except Exception as e:
            logging.error(f"Error getting checkpoint state from Redis for {session_id}: {e}")

        try:
            key = f"leadstate:{session_id}"
            leadstate_raw = await self.redis_client.get(key)
            leadstate = self._decode(leadstate_raw) or {}

            # Convert last_db_save_time back to datetime if it's a string
            last_db_save_time = leadstate.get("last_db_save_time")
            if isinstance(last_db_save_time, str):
                try:
                    leadstate["last_db_save_time"] = datetime.fromisoformat(last_db_save_time)
                except Exception:
                    leadstate["last_db_save_time"] = datetime.now()
        except Exception as e:
            logging.error(f"Error getting leadstate from Redis for {session_id}: {e}")

        if checkpoint_state and "messages" not in leadstate:
            leadstate["messages"] = checkpoint_state.get("messages", [])

        try:
            await self.redis_client.expire(key, SESSION_TTL_SECONDS)
            await self.redis_client.expire(session_id, SESSION_TTL_SECONDS)
        except Exception as e:
            logging.error(f"Error refreshing TTL in Redis for {session_id}: {e}")

        return leadstate

    async def save_state(self, session_id: str, state: Dict[str, Any]):
        try:
            # Serialize messages before saving checkpoint
            messages = state.get("messages", [])
            serializable_messages = self.serialize_messages(messages)
            checkpoint_data = {
                "messages": serializable_messages,
            }
            await self.checkpoint_saver.aset_tuple({"key": session_id}, checkpoint_data)
        except Exception as e:
            logging.error(f"Error saving checkpoint state to Redis for {session_id}: {e}")

        try:
            key = f"leadstate:{session_id}"

            # Prepare a copy and serialize datetime to string
            state_copy = dict(state)
            if "last_db_save_time" in state_copy and isinstance(state_copy["last_db_save_time"], datetime):
                state_copy["last_db_save_time"] = state_copy["last_db_save_time"].isoformat()

            data = self._encode(state_copy)
            await self.redis_client.set(key, data, ex=SESSION_TTL_SECONDS)
        except Exception as e:
            logging.error(f"Error saving leadstate to Redis for {session_id}: {e}")

    async def delete_state(self, session_id: str):
        try:
            await self.checkpoint_saver.aclear_tuple({"key": session_id})
        except Exception as e:
            logging.error(f"Error clearing checkpoint state in Redis for {session_id}: {e}")

        try:
            key = f"leadstate:{session_id}"
            await self.redis_client.delete(key)
        except Exception as e:
            logging.error(f"Error deleting leadstate in Redis for {session_id}: {e}")

hybrid_session_store = HybridRedisSessionStore()