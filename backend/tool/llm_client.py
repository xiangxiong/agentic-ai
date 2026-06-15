from __future__ import annotations

import inspect
import json
from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import Any, Callable, Union, get_args, get_origin

from openai import OpenAI

from config import Settings, get_settings

_TYPE_MAP = {
    str: "string",
    int: "integer",
    float: "number",
    bool: "boolean",
    list: "array",
    dict: "object",
}


def _json_type(annotation: Any) -> str:
    if annotation is inspect.Parameter.empty or annotation is Any:
        return "string"
    origin = get_origin(annotation)
    if origin is list:
        return "array"
    if origin is dict:
        return "object"
    if origin is type(None) or annotation is type(None):
        return "string"
    if origin is Union:
        args = [a for a in get_args(annotation) if a is not type(None)]
        if args:
            return _json_type(args[0])
    return _TYPE_MAP.get(annotation, "string")


def _function_to_tool(func: Callable[..., Any]) -> dict[str, Any]:
    doc = inspect.getdoc(func) or func.__name__
    description = doc.strip().split("\n\n")[0].replace("\n", " ")
    sig = inspect.signature(func)
    properties: dict[str, Any] = {}
    required: list[str] = []

    for name, param in sig.parameters.items():
        properties[name] = {"type": _json_type(param.annotation)}
        if param.default is inspect.Parameter.empty:
            required.append(name)

    return {
        "type": "function",
        "function": {
            "name": func.__name__,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required,
            },
        },
    }


@dataclass
class ChatChoice:
    message: Any
    intermediate_messages: list[Any] = field(default_factory=list)


@dataclass
class ChatCompletion:
    choices: list[ChatChoice]


class ChatCompletions:
    def __init__(self, client: OpenAI, settings: Settings) -> None:
        self._client = client
        self._settings = settings

    def create(
        self,
        *,
        model: str,
        messages: list[dict[str, Any]],
        tools: list[Callable[..., Any]],
        max_turns: int = 5,
        temperature: float = 0.0,
        **_: Any,
    ) -> ChatCompletion:
        tool_map = {tool.__name__: tool for tool in tools}
        tool_schemas = [_function_to_tool(tool) for tool in tools]
        conversation = list(messages)
        intermediate: list[Any] = []

        final_message: Any = SimpleNamespace(content="")

        for _ in range(max_turns):
            response = self._client.chat.completions.create(
                model=model,
                messages=conversation,
                tools=tool_schemas,
                temperature=temperature,
            )
            message = response.choices[0].message
            conversation.append(message.model_dump(exclude_none=True))

            if message.tool_calls:
                intermediate.append(message)
                for call in message.tool_calls:
                    func = tool_map[call.function.name]
                    args = json.loads(call.function.arguments or "{}")
                    try:
                        result = func(**args)
                        payload = json.dumps(result, ensure_ascii=False, default=str)
                    except Exception as exc:
                        payload = json.dumps({"error": str(exc)}, ensure_ascii=False)

                    tool_message = {
                        "role": "tool",
                        "tool_call_id": call.id,
                        "name": call.function.name,
                        "content": payload,
                    }
                    intermediate.append(tool_message)
                    conversation.append(tool_message)
                continue

            intermediate.append(message)
            final_message = message
            break

        return ChatCompletion(choices=[ChatChoice(message=final_message, intermediate_messages=intermediate)])


class ChatAPI:
    def __init__(self, client: OpenAI, settings: Settings) -> None:
        self.completions = ChatCompletions(client, settings)


class ZhipuToolClient:
    """OpenAI-compatible client with multi-turn tool calling for Zhipu GLM."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        if not self.settings.zhipu_api_key:
            raise ValueError(
                "ZHIPU_API_KEY is not set. Add it to backend/tool/.env or backend/.env."
            )
        self._client = OpenAI(
            api_key=self.settings.zhipu_api_key,
            base_url=self.settings.zhipu_base_url,
        )
        self.chat = ChatAPI(self._client, self.settings)
