from __future__ import annotations

from functools import lru_cache
from os import getenv
from typing import Optional

from dotenv import load_dotenv


load_dotenv()


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
    deepseek_temperature: float
    max_history_messages: int
    allowed_origins: list[str]
    system_prompt: str

    def __init__(self) -> None:
        self.deepseek_api_key = getenv("DEEPSEEK_API_KEY")
        self.deepseek_base_url = getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
        self.deepseek_model = getenv("DEEPSEEK_MODEL", "deepseek-v4-flash")
        self.deepseek_temperature = _get_float("DEEPSEEK_TEMPERATURE", 0.7)
        self.max_history_messages = _get_int("MAX_HISTORY_MESSAGES", 24)
        self.allowed_origins = _get_origins()
        self.system_prompt = getenv(
            "CHATBOT_SYSTEM_PROMPT",
            "You are a helpful, concise chatbot. Answer in the user's language.",
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
