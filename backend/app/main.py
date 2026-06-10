from __future__ import annotations

from collections.abc import AsyncIterator

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from app.chat_service import ChatService, MissingApiKeyError, sse_event
from app.config import get_settings
from app.schemas import ChatRequest, ChatResponse, HealthResponse


settings = get_settings()
chat_service = ChatService(settings)

app = FastAPI(title="DeepSeek LangChain Chatbot", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(status="ok", model=settings.deepseek_model)


@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    try:
        return await chat_service.chat(request)
    except MissingApiKeyError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/chat/stream")
async def chat_stream(request: ChatRequest) -> StreamingResponse:
    session_id = request.session_id or chat_service.create_session_id()

    async def event_stream() -> AsyncIterator[str]:
        yield sse_event("session", {"session_id": session_id})
        try:
            async for token in chat_service.stream(request, session_id):
                yield sse_event("token", {"content": token})
            yield sse_event("done", {"session_id": session_id})
        except MissingApiKeyError as exc:
            yield sse_event("error", {"message": str(exc)})
        except Exception:
            yield sse_event("error", {"message": "Chat completion failed."})

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@app.delete("/api/sessions/{session_id}", status_code=204)
async def clear_session(session_id: str) -> None:
    await chat_service.clear(session_id)
