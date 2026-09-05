"""
SQLAlchemy ORM models.

Schema (see docs/architecture.md for the full ER description):
  sessions          - one row per chat session
  messages          - one row per chat turn (user or assistant)
  artifacts         - generated markdown/html artifacts, linked to a message
  transcript_chunks - ingested podcast transcript chunks + embeddings (pgvector)
"""
import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import JSON, DateTime, ForeignKey, Index, String, Text, Uuid, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

# `Uuid`/`JSON` (generic SQLAlchemy 2.0 types) compile to native UUID/JSONB on
# Postgres and to portable equivalents on SQLite — this keeps the same model
# file usable for both the production Postgres DB and the fast in-memory
# SQLite test suite (see backend/tests/conftest.py).
UUID = Uuid
JSONB = JSON

EMBEDDING_DIM = 384  # matches all-MiniLM-L6-v2 / nomic-embed-text truncation


class Base(DeclarativeBase):
    pass


class ChatSession(Base):
    __tablename__ = "sessions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(255), default="New chat")
    llm_provider: Mapped[str] = mapped_column(String(32), default="ollama")
    user_metadata: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    messages: Mapped[list["Message"]] = relationship(
        back_populates="session", cascade="all, delete-orphan", order_by="Message.created_at"
    )


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sessions.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String(16))  # "user" | "assistant" | "system"
    content: Mapped[str] = mapped_column(Text)
    mode: Mapped[str] = mapped_column(String(16), default="default")  # "default" | "ship30"
    provider: Mapped[str] = mapped_column(String(32), default="ollama")
    sources: Mapped[list] = mapped_column(JSONB, default=list)  # cited transcript chunks
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    session: Mapped["ChatSession"] = relationship(back_populates="messages")
    artifacts: Mapped[list["Artifact"]] = relationship(back_populates="message", cascade="all, delete-orphan")


class Artifact(Base):
    __tablename__ = "artifacts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    message_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("messages.id", ondelete="CASCADE"), index=True)
    artifact_type: Mapped[str] = mapped_column(String(16))  # "markdown" | "html"
    title: Mapped[str] = mapped_column(String(255), default="Untitled artifact")
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    message: Mapped["Message"] = relationship(back_populates="artifacts")


class TranscriptChunk(Base):
    __tablename__ = "transcript_chunks"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    episode_title: Mapped[str] = mapped_column(String(500))
    guest_name: Mapped[str] = mapped_column(String(255), default="Unknown")
    source_path: Mapped[str] = mapped_column(String(1000))  # traceability back to raw transcript file
    chunk_index: Mapped[int] = mapped_column(default=0)
    chunk_text: Mapped[str] = mapped_column(Text)
    timestamp_ref: Mapped[str] = mapped_column(String(64), default="")
    embedding: Mapped[list[float]] = mapped_column(Vector(EMBEDDING_DIM))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index(
            "ix_transcript_chunks_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )
