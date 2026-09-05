"""Health endpoint — reports DB, Ollama, Anthropic, and vector-index status
independently so an evaluator (or on-call engineer) can diagnose which
component failed instead of getting a single opaque 500."""
import logging

from fastapi import APIRouter
from sqlalchemy import text

from app.config import get_settings
from app.database import check_db_connection, engine
from app.models.schemas import ComponentStatus, HealthResponse
from app.providers.factory import get_provider

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["Health"])


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    settings = get_settings()

    db_ok = await check_db_connection()
    database = ComponentStatus(status="ok" if db_ok else "down", detail="" if db_ok else "cannot connect")

    vector_index = ComponentStatus(status="down", detail="database unreachable")
    if db_ok:
        try:
            async with engine.connect() as conn:
                result = await conn.execute(text("SELECT count(*) FROM transcript_chunks"))
                count = result.scalar_one()
                vector_index = (
                    ComponentStatus(status="ok", detail=f"{count} chunks indexed")
                    if count > 0
                    else ComponentStatus(status="degraded", detail="table exists but 0 chunks ingested")
                )
        except Exception as exc:  # noqa: BLE001
            vector_index = ComponentStatus(status="down", detail=f"table missing or query failed: {exc}")

    ollama_provider, _ = get_provider("ollama", settings)
    ollama_ok, ollama_detail = await ollama_provider.health_check()
    ollama = ComponentStatus(status="ok" if ollama_ok else "down", detail=ollama_detail)

    if settings.anthropic_configured:
        anthropic_provider, _ = get_provider("anthropic", settings)
        a_ok, a_detail = await anthropic_provider.health_check()
        anthropic = ComponentStatus(status="ok" if a_ok else "down", detail=a_detail)
    else:
        anthropic = ComponentStatus(status="degraded", detail="not configured (optional)")

    statuses = [database.status, ollama.status]  # only required components gate overall health
    overall = "ok" if all(s == "ok" for s in statuses) else ("down" if "down" in statuses else "degraded")

    return HealthResponse(
        status=overall, database=database, ollama=ollama, anthropic=anthropic, vector_index=vector_index
    )
