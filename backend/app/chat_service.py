from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from typing import Optional
from uuid import uuid4

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from app.config import Settings
from app.schemas import ChatMessage, ChatRequest, CoplotRequest,ChatResponse, Source


class MissingApiKeyError(RuntimeError):
    pass


class ConversationStore:
    def __init__(self, max_messages: int) -> None:
        self._messages: dict[str, list[BaseMessage]] = {}
        self._max_messages = max_messages
        self._lock = asyncio.Lock()

    async def get(self, session_id: str) -> list[BaseMessage]:
        async with self._lock:
            return list(self._messages.get(session_id, []))

    async def append(self, session_id: str, messages: list[BaseMessage]) -> list[BaseMessage]:
        async with self._lock:
            current = self._messages.setdefault(session_id, [])
            current.extend(messages)
            if len(current) > self._max_messages:
                del current[: len(current) - self._max_messages]
            return list(current)

    async def clear(self, session_id: str) -> None:
        async with self._lock:
            self._messages.pop(session_id, None)


class ChatService:
    def __init__(self, settings: Settings, rag_service: Optional[object] = None) -> None:
        self._settings = settings
        self._store = ConversationStore(max_messages=settings.max_history_messages)
        self._rag_service = rag_service

    def create_session_id(self) -> str:
        return uuid4().hex

    def _build_llm(self, streaming: bool = False) -> ChatOpenAI:
        if not self._settings.zhipu_api_key:
            raise MissingApiKeyError("ZHIPU_API_KEY is not configured.")

        return ChatOpenAI(
            api_key=self._settings.zhipu_api_key,
            base_url=self._settings.zhipu_base_url,
            model=self._settings.zhipu_model,
            temperature=self._settings.deepseek_temperature,
            streaming=streaming,
        )

    async def _build_messages(
        self, request: ChatRequest, session_id: str
    ) -> tuple[list[BaseMessage], list[Source]]:
        system_prompt = request.system_prompt or self._settings.system_prompt
        sources: list[Source] = []

        if request.use_knowledge_base and request.knowledge_base_id and self._rag_service:
            top_k = request.top_k or self._settings.rag_top_k
            context, sources = self._rag_service.retrieve(
                request.knowledge_base_id,
                request.message,
                top_k,
            )

            if context:
                system_prompt = (
                    f"{system_prompt}\n\n"
                    "Use the following knowledge base context when relevant. "
                    "If the context does not contain enough information, say so clearly. "
                    "Do not invent facts that are not supported by the context.\n\n"
                    f"{context}"
                )

        history = await self._store.get(session_id)
        messages = [SystemMessage(content=system_prompt), *history, HumanMessage(content=request.message)]
        return messages, sources

    async def chat(self, request: ChatRequest) -> ChatResponse:
        session_id = request.session_id or self.create_session_id()
        llm = self._build_llm()
        messages, sources = await self._build_messages(request, session_id)

        response = await llm.ainvoke(messages)
        answer = str(response.content)
        history = await self._store.append(
            session_id,
            [HumanMessage(content=request.message), AIMessage(content=answer)],
        )

        return ChatResponse(
            session_id=session_id,
            message=answer,
            history=self._serialize_history(history),
            sources=sources,
        )

    async def stream1(self, request: CoplotRequest, session_id: str) -> AsyncIterator[tuple[str, object]]:
        try:
            llm = self._build_llm(streaming=True)
            messages, sources = await self._build_messages(request, session_id)

            chunks:list[str] = [];
            yield "sources", [source.model_dump() for source in sources]
            async for chunk in llm.astream(messages):
                content = chunk.content
                if isinstance(content, str) and content:
                    chunks.append(content);
                    yield "token", content

            answer = "".join(chunks);
            await self._store.append(
                session_id,
                [HumanMessage(content=request.message), AIMessage(content=answer)],
            )

        except Exception as e:
            print('stream1 error:', type(e).__name__, e)
            raise;

    async def stream(self, request: ChatRequest, session_id: str) -> AsyncIterator[tuple[str, object]]:
        llm = self._build_llm(streaming=True)
        print('request', request);
        print('session_id', session_id);
        messages, sources = await self._build_messages(request, session_id)
        print('messages', messages);
        print('sources', sources);
        chunks: list[str] = []

        yield "sources", [source.model_dump() for source in sources]

        async for chunk in llm.astream(messages):
            content = chunk.content
            if isinstance(content, str) and content:
                chunks.append(content)
                yield "token", content

        answer = "".join(chunks)
        await self._store.append(
            session_id,
            [HumanMessage(content=request.message), AIMessage(content=answer)],
        )

    async def clear(self, session_id: str) -> None:
        await self._store.clear(session_id)

    def _serialize_history(self, messages: list[BaseMessage]) -> list[ChatMessage]:
        serialized: list[ChatMessage] = []
        for message in messages:
            if isinstance(message, HumanMessage):
                role = "user"
            elif isinstance(message, AIMessage):
                role = "assistant"
            else:
                continue
            serialized.append(ChatMessage(role=role, content=str(message.content)))
        return serialized

def sse_event(event: str, payload: dict[str, object]) -> str:
    return f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"
