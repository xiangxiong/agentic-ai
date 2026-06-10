from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class Source(BaseModel):
    document_id: str
    filename: str
    chunk_id: str
    content: str


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=8000)
    session_id: Optional[str] = Field(default=None, max_length=100)
    system_prompt: Optional[str] = Field(default=None, max_length=4000)
    use_knowledge_base: bool = False
    knowledge_base_id: Optional[str] = Field(default=None, max_length=100)
    top_k: Optional[int] = Field(default=None, ge=1, le=10)


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatResponse(BaseModel):
    session_id: str
    message: str
    history: list[ChatMessage]
    sources: list[Source] = Field(default_factory=list)


class DocumentUploadResponse(BaseModel):
    knowledge_base_id: str
    document_id: str
    filename: str
    chunks: int


class HealthResponse(BaseModel):
    status: str
    model: str
