from datetime import datetime, timezone
from enum import Enum
from uuid import uuid4

from sqlmodel import Field, SQLModel


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _new_id() -> str:
    return uuid4().hex


class DocumentStatus(str, Enum):
    processing = "processing"
    ready = "ready"
    failed = "failed"


class Document(SQLModel, table=True):
    """Registry of uploaded files. Vectors live in Chroma; this table is the source of truth for status."""

    id: str = Field(default_factory=_new_id, primary_key=True)
    filename: str  # original name shown to the user
    stored_name: str  # name on disk inside docs_dir
    sha256: str = Field(index=True, unique=True)
    size_bytes: int
    page_count: int | None = None
    chunk_count: int | None = None
    status: DocumentStatus = DocumentStatus.processing
    error: str | None = None
    created_at: datetime = Field(default_factory=_utcnow)


class Conversation(SQLModel, table=True):
    id: str = Field(default_factory=_new_id, primary_key=True)
    title: str
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)


class Message(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    conversation_id: str = Field(foreign_key="conversation.id", index=True)
    role: str  # "user" | "assistant"
    content: str
    sources_json: str | None = None  # JSON list of cited sources for assistant messages
    rewritten_query: str | None = None  # standalone query used for retrieval
    created_at: datetime = Field(default_factory=_utcnow)
