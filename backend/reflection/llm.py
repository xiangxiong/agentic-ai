from __future__ import annotations

import json
import re
from typing import Any

from openai import OpenAI

from config import Settings, get_settings


class ZhipuClient:
    """Thin wrapper around the OpenAI-compatible Zhipu API."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        if not self.settings.zhipu_api_key:
            raise ValueError(
                "ZHIPU_API_KEY is not set. Add it to backend/reflection/.env "
                "or backend/.env."
            )
        self._client = OpenAI(
            api_key=self.settings.zhipu_api_key,
            base_url=self.settings.zhipu_base_url,
        )

    def chat(
        self,
        prompt: str,
        *,
        model: str,
        temperature: float,
    ) -> str:
        response = self._client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature,
        )
        content = response.choices[0].message.content
        if not content:
            raise ValueError("Model returned an empty response.")
        return content.strip()


def parse_json_object(content: str) -> dict[str, Any]:
    """Parse JSON from a model response, tolerating markdown fences."""
    text = content.strip()
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fenced:
        text = fenced.group(1)
    else:
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            text = text[start : end + 1]
    return json.loads(text)
