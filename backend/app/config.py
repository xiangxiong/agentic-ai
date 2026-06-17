from __future__ import annotations

from functools import lru_cache
from os import getenv
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

_BACKEND_DIR = Path(__file__).resolve().parent.parent
load_dotenv(_BACKEND_DIR / ".env")
load_dotenv(_BACKEND_DIR / "reflection" / ".env")


def _get_float(name: str, default: float) -> float:
    value = getenv(name)
    if value is None or value == "":
        return default
    try:
        return float(value)
    except ValueError:
        return default


def _get_int(name: str, default: int) -> int:
    value = getenv(name)
    if value is None or value == "":
        return default
    try:
        return int(value)
    except ValueError:
        return default


def _get_origins() -> list[str]:
    value = getenv("ALLOWED_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173")
    return [origin.strip() for origin in value.split(",") if origin.strip()]


class Settings:
    deepseek_api_key: Optional[str]
    deepseek_base_url: str
    deepseek_model: str
    zhipu_api_key: Optional[str]
    zhipu_base_url: str
    zhipu_model: str
    zhipu_embedding_model: str
    deepseek_temperature: float
    max_history_messages: int
    allowed_origins: list[str]
    system_prompt: str
    rag_storage_dir: str
    rag_embedding_model: str
    rag_chunk_size: int
    rag_chunk_overlap: int
    rag_top_k: int

    def __init__(self) -> None:
        self.deepseek_api_key = getenv("DEEPSEEK_API_KEY")
        self.deepseek_base_url = getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
        self.deepseek_model = getenv("DEEPSEEK_MODEL", "deepseek-v4-flash")
        self.zhipu_api_key = getenv("ZHIPU_API_KEY")
        self.zhipu_base_url = getenv(
            "ZHIPU_BASE_URL",
            "https://open.bigmodel.cn/api/paas/v4/",
        )
        self.zhipu_model = getenv("ZHIPU_MODEL", getenv("ZHIPU_MODEL_GENERATION", "glm-4-flash"))
        self.zhipu_embedding_model = getenv("ZHIPU_EMBEDDING_MODEL", "embedding-3")
        self.deepseek_temperature = _get_float("DEEPSEEK_TEMPERATURE", 0.7)
        self.max_history_messages = _get_int("MAX_HISTORY_MESSAGES", 24)
        self.allowed_origins = _get_origins()
        self.system_prompt = getenv(
            "CHATBOT_SYSTEM_PROMPT",
            "You are a helpful, concise chatbot. Answer in the user's language.",
        )
        self.rag_storage_dir = getenv("RAG_STORAGE_DIR", "storage")
        self.rag_embedding_model = getenv("RAG_EMBEDDING_MODEL", "BAAI/bge-small-zh-v1.5")
        self.rag_chunk_size = _get_int("RAG_CHUNK_SIZE", 800)
        self.rag_chunk_overlap = _get_int("RAG_CHUNK_OVERLAP", 120)
        self.rag_top_k = _get_int("RAG_TOP_K", 4)

@lru_cache
def get_settings() -> Settings:
    return Settings()
