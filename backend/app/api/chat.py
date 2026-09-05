"""
Core chat endpoint.

Flow per request:
  1. Load session + recent history (context preservation across turns).
  2. Resolve LLM provider (explicit > session default > global default),
     falling back Anthropic -> Ollama transparently when no API key is set.
  3. Retrieve relevant transcript chunks for the user's message.
  4. Build a mode-specific system prompt:
       - "default": grounded Q&A, must say so when context is insufficient.
       - "ship30":  Ship 30 for 30 essay skill.
       - "artifact": same grounded Q&A, but instructed it may emit an
         <artifact> block if the user is asking for a document/snippet.
  5. Stream tokens back over SSE; on completion, extract any artifact,
     persist the user message + assistant message + artifact, and emit a
     final "sources"/"done" event with citations and the persisted IDs.

Failure handling: missing session -> 404. Provider unreachable -> the stream
emits a typed "error" SSE event (not a raw 500, since headers are already
flushed) with a clear message, and nothing partial is persisted as if it
succeeded.
"""
import json
import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.database import get_db
from app.models.db_models import Artifact, ChatSession, Message
from app.models.schemas import ChatRequest
from app.providers.base import ProviderUnavailableError
from app.providers.factory import get_embedding_provider, get_provider
from app.rag.retriever import TranscriptRetriever
from app.skills.artifact_generator import ARTIFACT_SYSTEM_PROMPT, extract_artifact
from app.skills.ship30_writer import SHIP30_SYSTEM_PROMPT, build_ship30_prompt

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/chat", tags=["Chat"])

DEFAULT_SYSTEM_PROMPT = """You are the Lenny Growth Assistant, a product/growth expert \
that answers strictly from the provided Lenny's Podcast transcript context.

Rules:
- Ground every specific claim in the provided context and cite the episode/guest inline,
  e.g. "According to [Guest] on [Episode]...".
- If the context does not support an answer, say plainly: "I don't have enough
  information in Lenny's podcast archive to answer that confidently," and optionally
  offer a general, clearly-labeled non-grounded perspective if asked to.
- Keep answers concise and skimmable unless the user asks for depth.
- You have access to the ongoing conversation for follow-up questions — use it."""


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


@router.post("")
async def stream_chat(
    req: ChatRequest,
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    session = await db.get(ChatSession, req.session_id)
    if session is None:
        raise HTTPException(status_code=404, detail=f"Session {req.session_id} not found")

    provider, fell_back = get_provider(req.provider or session.llm_provider, settings)
    embed_provider = get_embedding_provider(settings)
    retriever = TranscriptRetriever(db, embed_provider)

    # Persist the user's message immediately so it survives even if generation fails.
    user_message = Message(session_id=session.id, role="user", content=req.message, mode=req.mode)
    db.add(user_message)
    await db.commit()

    # Recent history for follow-up context (last 10 turns).
    history_result = await db.execute(
        select(Message).where(Message.session_id == session.id).order_by(Message.created_at).limit(20)
    )
    history = [
        {"role": m.role, "content": m.content}
        for m in history_result.scalars().all()
        if m.role in ("user", "assistant")
    ]

    async def event_stream():
        yield _sse("status", {"message": "Retrieving transcripts..."})

        try:
            chunks = await retriever.retrieve(
                req.message,
                top_k=settings.retrieval_top_k,
                similarity_threshold=settings.retrieval_similarity_threshold,
            )
        except ProviderUnavailableError as exc:
            logger.error("retrieval_failed", extra={"event": "retrieval_error", "session_id": str(session.id)})
            yield _sse("error", {"message": f"Retrieval unavailable: {exc}"})
            return

        if fell_back:
            yield _sse(
                "status",
                {"message": "Anthropic not configured — using local Ollama model instead."},
            )

        if req.mode == "ship30":
            system_prompt = SHIP30_SYSTEM_PROMPT
            user_turn = build_ship30_prompt(req.message, chunks)
        else:
            system_prompt = DEFAULT_SYSTEM_PROMPT + "\n\n" + ARTIFACT_SYSTEM_PROMPT
            context_block = (
                "\n\n".join(
                    f"[{c['episode']} — {c['guest']}, {c['timestamp']}]\n{c['text']}" for c in chunks
                )
                if chunks
                else "(No transcript chunks cleared the relevance threshold for this query.)"
            )
            user_turn = f"Transcript context:\n{context_block}\n\nUser question: {req.message}"

        messages = [*history[:-1], {"role": "user", "content": user_turn}]

        full_text = ""
        try:
            async for token in provider.stream_chat(messages, system_prompt, temperature=0.3):
                full_text += token
                yield _sse("token", {"content": token})
        except ProviderUnavailableError as exc:
            logger.error(
                "generation_failed",
                extra={"event": "provider_error", "session_id": str(session.id), "provider": provider.name},
            )
            yield _sse("error", {"message": str(exc)})
            return

        chat_reply, artifact = extract_artifact(full_text)

        assistant_message = Message(
            session_id=session.id,
            role="assistant",
            content=chat_reply,
            mode=req.mode,
            provider=provider.name,
            sources=[
                {"episode": c["episode"], "guest": c["guest"], "timestamp": c["timestamp"], "score": c["score"]}
                for c in chunks
            ],
        )
        db.add(assistant_message)
        await db.flush()

        artifact_payload = None
        if artifact:
            db_artifact = Artifact(
                message_id=assistant_message.id,
                artifact_type=artifact.artifact_type,
                title=artifact.title,
                content=artifact.content,
            )
            db.add(db_artifact)
            await db.flush()
            artifact_payload = {
                "id": str(db_artifact.id),
                "type": db_artifact.artifact_type,
                "title": db_artifact.title,
                "content": db_artifact.content,
            }

        await db.commit()

        yield _sse(
            "done",
            {
                "message_id": str(assistant_message.id),
                "sources": assistant_message.sources,
                "artifact": artifact_payload,
                "provider": provider.name,
            },
        )

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
