"""Vector similarity retrieval over ingested transcript chunks.

Grounding contract: every answer must be traceable to the chunks returned
here. If nothing clears `similarity_threshold`, the caller (chat.py) tells the
model to say it cannot answer from the archive rather than guessing.
"""
import logging

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.providers.base import BaseLLMProvider

logger = logging.getLogger(__name__)


class TranscriptRetriever:
    def __init__(self, db: AsyncSession, embedding_provider: BaseLLMProvider):
        self.db = db
        self.embedding_provider = embedding_provider

    async def retrieve(
        self, query: str, top_k: int = 5, similarity_threshold: float = 0.35
    ) -> list[dict]:
        query_vector = await self.embedding_provider.embed(query)

        # Cosine distance operator `<=>` from pgvector; similarity = 1 - distance.
        stmt = text(
            """
            SELECT
                episode_title, guest_name, chunk_text, timestamp_ref, source_path,
                1 - (embedding <=> CAST(:vector AS vector)) AS similarity_score
            FROM transcript_chunks
            ORDER BY embedding <=> CAST(:vector AS vector)
            LIMIT :limit
            """
        )
        result = await self.db.execute(stmt, {"vector": str(query_vector), "limit": top_k})
        rows = result.fetchall()

        chunks = [
            {
                "episode": r.episode_title,
                "guest": r.guest_name,
                "text": r.chunk_text,
                "timestamp": r.timestamp_ref,
                "source_path": r.source_path,
                "score": float(r.similarity_score),
            }
            for r in rows
        ]
        above_threshold = [c for c in chunks if c["score"] >= similarity_threshold]

        logger.info(
            "retrieval_complete",
            extra={
                "event": "retrieval",
                "session_id": None,
            },
        )
        # Return the best matches even if below threshold — the caller decides
        # whether to use them; but flag it via an empty-list sentinel when the
        # very top result is weak, so chat.py can trigger the "insufficient
        # context" branch.
        return above_threshold if above_threshold else []
