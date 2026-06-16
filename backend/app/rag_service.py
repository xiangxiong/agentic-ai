from __future__ import annotations
import re
from pathlib import Path
from typing import Optional
from uuid import uuid4
from fastapi import UploadFile
from langchain_chroma import Chroma
from langchain_community.document_loaders import TextLoader
from langchain_core.documents import Document
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from app.config import Settings
from app.schemas import Source

class RagService:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._storage_dir = Path(settings.rag_storage_dir)
        self._uploads_dir = self._storage_dir / "uploads"
        self._chroma_dir = self._storage_dir / "chroma"
        self._embeddings: Optional[HuggingFaceEmbeddings] = None
        self._splitter = RecursiveCharacterTextSplitter(
            chunk_size=settings.rag_chunk_size,
            chunk_overlap=settings.rag_chunk_overlap,
        )

    async def upload_document(self, kb_id: str, file: UploadFile) -> tuple[str, int]:
        safe_kb_id = self._validate_kb_id(kb_id)
        filename = self._validate_filename(file.filename)
        document_id = uuid4().hex

        kb_upload_dir = self._uploads_dir / safe_kb_id
        kb_upload_dir.mkdir(parents=True, exist_ok=True)

        saved_path = kb_upload_dir / f"{document_id}-{filename}"
        saved_path.write_bytes(await file.read())

        docs = TextLoader(str(saved_path), encoding="utf-8").load()
        for doc in docs:
            doc.metadata.update(
                {
                    "knowledge_base_id": safe_kb_id,
                    "document_id": document_id,
                    "filename": filename,
                    "source": str(saved_path),
                }
            )

        chunks = self._splitter.split_documents(docs)
        for index, chunk in enumerate(chunks):
            chunk.metadata["chunk_id"] = f"{document_id}-{index}"

        if chunks:
            self._vectorstore(safe_kb_id).add_documents(chunks)

        return document_id, len(chunks)

    def retrieve(self, kb_id: str, query: str, top_k: int) -> tuple[str, list[Source]]:
        safe_kb_id = self._validate_kb_id(kb_id)
        docs = self._vectorstore(safe_kb_id).similarity_search(query, k=top_k)
        sources = [self._to_source(doc) for doc in docs]

        context = "\n\n".join(
            f"[{index + 1}] {source.filename}\n{source.content}"
            for index, source in enumerate(sources)
        )
        return context, sources

    def _vectorstore(self, kb_id: str) -> Chroma:
        return Chroma(
            collection_name=f"kb_{kb_id}",
            persist_directory=str(self._chroma_dir / kb_id),
            embedding_function=self._get_embeddings(),
        )

    def _get_embeddings(self) -> HuggingFaceEmbeddings:
        if self._embeddings is None:
            self._embeddings = HuggingFaceEmbeddings(model_name=self._settings.rag_embedding_model)
        return self._embeddings

    def _to_source(self, doc: Document) -> Source:
        return Source(
            document_id=str(doc.metadata.get("document_id", "")),
            filename=str(doc.metadata.get("filename", "")),
            chunk_id=str(doc.metadata.get("chunk_id", "")),
            content=doc.page_content,
        )

    def _validate_kb_id(self, kb_id: str) -> str:
        if not re.fullmatch(r"[a-zA-Z0-9](?:[a-zA-Z0-9_-]{0,62}[a-zA-Z0-9])?", kb_id):
            raise ValueError(
                "knowledge_base_id must be 1-64 characters and may only contain letters, "
                "numbers, underscores, and hyphens. It must start and end with a letter or number."
            )
        return kb_id

    def _validate_filename(self, filename: Optional[str]) -> str:
        if not filename:
            raise ValueError("Filename is required.")

        safe_name = Path(filename).name
        if not safe_name.lower().endswith((".txt", ".md")):
            raise ValueError("Only .txt and .md files are supported.")

        return safe_name
