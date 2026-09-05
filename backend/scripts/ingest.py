#!/usr/bin/env python3
"""
Chunks transcript files from backend/data/transcripts/ and loads them into
the `transcript_chunks` pgvector table.

USAGE
  python scripts/ingest.py [--reset]

Pipeline
  1. Read every .json/.txt/.md file in data/transcripts/.
  2. Split into ~CHUNK_TOKEN_SIZE-word chunks with CHUNK_TOKEN_OVERLAP overlap
     (recursive character/word splitting — good enough for transcript prose
     without adding a tokenizer dependency).
  3. Embed each chunk via the configured embedding provider (Ollama by
     default — keeps ingestion fully local).
  4. Upsert into Postgres with source_path + chunk_index preserved, so every
     answer can cite back to "which file, which chunk" for traceability.

Re-running ingest.py is idempotent per source_path+chunk_index when --reset
is not passed (it skips files already ingested); pass --reset to wipe and
reload everything, e.g. after changing chunk size.
"""
import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import delete, select  # noqa: E402

from app.config import get_settings  # noqa: E402
from app.database import db_session_ctx  # noqa: E402
from app.models.db_models import TranscriptChunk  # noqa: E402
from app.providers.factory import get_embedding_provider  # noqa: E402

logging.basicConfig(level="INFO", format="%(levelname)s %(message)s")
logger = logging.getLogger("ingest")

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "transcripts"


def load_documents() -> list[dict]:
    docs = []
    for f in sorted(DATA_DIR.glob("*")):
        if f.suffix == ".json":
            record = json.loads(f.read_text())
            docs.append(
                {
                    "title": record.get("title", f.stem),
                    "guest": record.get("guest", "Unknown"),
                    "text": record.get("text", ""),
                    "source_path": str(f.relative_to(DATA_DIR.parent.parent)),
                }
            )
        elif f.suffix in (".txt", ".md"):
            docs.append(
                {
                    "title": f.stem.replace("_", " ").title(),
                    "guest": "Unknown",
                    "text": f.read_text(),
                    "source_path": str(f.relative_to(DATA_DIR.parent.parent)),
                }
            )
    return docs


def chunk_text(text: str, size_words: int, overlap_words: int) -> list[str]:
    words = text.split()
    if not words:
        return []
    chunks, start = [], 0
    while start < len(words):
        end = min(start + size_words, len(words))
        chunks.append(" ".join(words[start:end]))
        if end == len(words):
            break
        start = end - overlap_words
    return chunks


async def run(reset: bool) -> None:
    settings = get_settings()
    embed_provider = get_embedding_provider(settings)

    healthy, detail = await embed_provider.health_check()
    if not healthy:
        logger.error(
            "Embedding provider (Ollama) is unreachable (%s). Start Ollama and "
            "`ollama pull %s` before ingesting.",
            detail,
            settings.ollama_embed_model,
        )
        sys.exit(1)

    documents = load_documents()
    if not documents:
        logger.warning(
            "No files found in %s. Run scripts/download_transcripts.py first.", DATA_DIR
        )
        return

    async with db_session_ctx() as db:
        if reset:
            await db.execute(delete(TranscriptChunk))
            await db.commit()
            logger.info("Reset: cleared existing transcript_chunks")

        total_chunks = 0
        for doc in documents:
            existing = await db.execute(
                select(TranscriptChunk.id).where(TranscriptChunk.source_path == doc["source_path"])
            )
            if existing.first() and not reset:
                logger.info("Skipping already-ingested %s", doc["source_path"])
                continue

            pieces = chunk_text(doc["text"], settings.chunk_token_size, settings.chunk_token_overlap)
            for idx, piece in enumerate(pieces):
                vector = await embed_provider.embed(piece)
                db.add(
                    TranscriptChunk(
                        episode_title=doc["title"],
                        guest_name=doc["guest"],
                        source_path=doc["source_path"],
                        chunk_index=idx,
                        chunk_text=piece,
                        timestamp_ref=f"chunk {idx + 1}/{len(pieces)}",
                        embedding=vector,
                    )
                )
                total_chunks += 1
            await db.commit()
            logger.info("Ingested %s -> %d chunks", doc["title"], len(pieces))

        logger.info("Ingestion complete: %d documents, %d total chunks", len(documents), total_chunks)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reset", action="store_true", help="Wipe existing chunks before ingesting")
    args = parser.parse_args()
    asyncio.run(run(reset=args.reset))


if __name__ == "__main__":
    main()
