from __future__ import annotations

from collections.abc import AsyncIterator

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from app.chat_service import ChatService, MissingApiKeyError, sse_event
from app.config import get_settings
from app.rag_service import RagService
from app.schemas import ChatRequest, ChatResponse, DocumentUploadResponse, HealthResponse


settings = get_settings()
rag_service = RagService(settings)
chat_service = ChatService(settings, rag_service)

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
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except MissingApiKeyError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/chat/stream")
async def chat_stream(request: ChatRequest) -> StreamingResponse:
    session_id = request.session_id or chat_service.create_session_id()

    async def event_stream() -> AsyncIterator[str]:
        yield sse_event("session", {"session_id": session_id})
        try:
            async for event, payload in chat_service.stream(request, session_id):
                if event == "sources":
                    yield sse_event("sources", {"sources": payload})
                else:
                    yield sse_event("token", {"content": payload})
            yield sse_event("done", {"session_id": session_id})
        except ValueError as exc:
            yield sse_event("error", {"message": str(exc)})
        except MissingApiKeyError as exc:
            yield sse_event("error", {"message": str(exc)})
        except Exception:
            yield sse_event("error", {"message": "Chat completion failed."})

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@app.post("/api/knowledge-bases/{kb_id}/documents", response_model=DocumentUploadResponse)
async def upload_knowledge_document(
    kb_id: str,
    file: UploadFile = File(...),
) -> DocumentUploadResponse:
    try:
        document_id, chunks = await rag_service.upload_document(kb_id, file)
        return DocumentUploadResponse(
            knowledge_base_id=kb_id,
            document_id=document_id,
            filename=file.filename or "",
            chunks=chunks,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.delete("/api/sessions/{session_id}", status_code=204)
async def clear_session(session_id: str) -> None:
    await chat_service.clear(session_id)
