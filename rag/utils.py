from langchain_openai import ChatOpenAI
from langchain_community.embeddings import HuggingFaceEmbeddings
import os
import yaml
from typing import Dict, Any


class Utils:
    def __init__(self, config_path: str = "config.yaml"):
        self.config = self._load_config(config_path)

    def _load_config(self, config_path: str) -> Dict[str, Any]:
        try:
            with open(config_path, "r") as f:
                return yaml.safe_load(f)
        except Exception as e:
            raise RuntimeError(f"Failed to load config: {e}")

    def initialize_llm(self):
        groq = self.config["model"]["groq"]
        api_key = os.getenv(groq["api_key_env"])
        if not api_key:
            raise RuntimeError("Groq API key missing")

        return ChatOpenAI(
            model=groq["model_name"],
            temperature=groq["temperature"],
            max_tokens=groq["max_tokens"],
            api_key=api_key,
            base_url=groq.get("api_url")
        )

    def initialize_embeddings(self):
        return HuggingFaceEmbeddings(model_name=self.config["embeddings"]["HuggingFaceEmbeddings"]["model_name"])
