"""Pydantic request/response contracts for the API."""
import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


# ---------- Sessions ----------

class CreateSessionRequest(BaseModel):
    title: str | None = Field(default=None, max_length=255)
    llm_provider: Literal["ollama", "anthropic"] = "ollama"


class SessionResponse(BaseModel):
    id: uuid.UUID
    title: str
    llm_provider: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ---------- Messages / Chat ----------

class SourceCitation(BaseModel):
    episode: str
    guest: str
    timestamp: str = ""
    score: float


class MessageResponse(BaseModel):
    id: uuid.UUID
    role: str
    content: str
    mode: str
    provider: str
    sources: list[SourceCitation] = []
    created_at: datetime

    class Config:
        from_attributes = True


class SessionDetailResponse(SessionResponse):
    messages: list[MessageResponse] = []


class ChatRequest(BaseModel):
    session_id: uuid.UUID
    message: str = Field(min_length=1, max_length=8000)
    mode: Literal["default", "ship30", "artifact"] = "default"
    provider: Literal["ollama", "anthropic"] | None = None  # None = use session default


# ---------- Errors ----------

class ErrorDetail(BaseModel):
    error: str
    detail: str
    request_id: str | None = None


# ---------- Health ----------

class ComponentStatus(BaseModel):
    status: Literal["ok", "degraded", "down"]
    detail: str = ""


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded", "down"]
    database: ComponentStatus
    ollama: ComponentStatus
    anthropic: ComponentStatus
    vector_index: ComponentStatus
