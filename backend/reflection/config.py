from __future__ import annotations

from functools import lru_cache
from os import getenv
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

_REFLECTION_DIR = Path(__file__).resolve().parent
load_dotenv(_REFLECTION_DIR / ".env")
load_dotenv(_REFLECTION_DIR.parent / ".env")

def _get_float(name: str, default: float) -> float:
    value = getenv(name)
    if not value:
        return default
    try:
        return float(value)
    except ValueError:
        return default


class Settings:
    zhipu_api_key: Optional[str]
    zhipu_base_url: str
    zhipu_model_generation: str
    zhipu_model_evaluation: str
    zhipu_temperature_generation: float
    zhipu_temperature_evaluation: float
    default_db_path: str

    def __init__(self) -> None:
        self.zhipu_api_key = getenv("ZHIPU_API_KEY")
        self.zhipu_base_url = getenv(
            "ZHIPU_BASE_URL",
            "https://open.bigmodel.cn/api/paas/v4/",
        )
        self.zhipu_model_generation = getenv("ZHIPU_MODEL_GENERATION", "glm-4-flash")
        self.zhipu_model_evaluation = getenv("ZHIPU_MODEL_EVALUATION", "glm-4-plus")
        self.zhipu_temperature_generation = _get_float("ZHIPU_TEMPERATURE_GENERATION", 0.0)
        self.zhipu_temperature_evaluation = _get_float("ZHIPU_TEMPERATURE_EVALUATION", 0.3)
        self.default_db_path = getenv("REFLECTION_DB_PATH", "products.db")


@lru_cache
def get_settings() -> Settings:
    return Settings()
