from __future__ import annotations

import os

from app.config import Settings


def configure_langsmith(settings: Settings) -> None:
    """Apply LangSmith env vars before any traced LLM or Copilot calls."""
    if not settings.langsmith_tracing_enabled:
        return

    os.environ["LANGCHAIN_TRACING_V2"] = "true"

    if settings.langsmith_api_key:
        os.environ["LANGCHAIN_API_KEY"] = settings.langsmith_api_key

    if settings.langsmith_project:
        os.environ["LANGCHAIN_PROJECT"] = settings.langsmith_project
