from __future__ import annotations

from functools import lru_cache
from os import getenv
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

_TOOL_DIR = Path(__file__).resolve().parent
load_dotenv(_TOOL_DIR / ".env")
load_dotenv(_TOOL_DIR.parent / ".env")
load_dotenv(_TOOL_DIR.parent / "reflection" / ".env")


class Settings:
    zhipu_api_key: Optional[str]
    zhipu_base_url: str
    zhipu_model: str
    email_server_url: str

    def __init__(self) -> None:
        self.zhipu_api_key = getenv("ZHIPU_API_KEY")
        self.zhipu_base_url = getenv(
            "ZHIPU_BASE_URL",
            "https://open.bigmodel.cn/api/paas/v4/",
        )
        self.zhipu_model = getenv("ZHIPU_MODEL", "glm-4-flash")
        self.email_server_url = getenv(
            "M3_EMAIL_SERVER_API_URL",
            "http://127.0.0.1:8020",
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
