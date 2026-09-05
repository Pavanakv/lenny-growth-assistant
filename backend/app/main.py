"""
FastAPI application entrypoint.

Wires together: CORS, structured logging, a request-id middleware, global
exception handlers (so every error is a structured JSON body, never a raw
traceback), and the three routers (health, sessions, chat).
"""
import logging
import time
import uuid

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from contextlib import asynccontextmanager

from sqlalchemy import text

from app.api import chat, health, sessions
from app.config import get_settings
from app.database import engine
from app.logging_config import configure_logging
from app.models.db_models import Base

settings = get_settings()
configure_logging(settings.log_level)
logger = logging.getLogger("lenny_growth_assistant")


@asynccontextmanager
async def lifespan(_: FastAPI):
    # Best-effort schema bootstrap: enables pgvector and creates any missing
    # tables. Failures here must NOT crash the process — /api/health will
    # simply report the database as down so the evaluator gets a clear
    # signal instead of a boot-loop. A production deployment would replace
    # this with a proper migration tool (see README "Handoff notes").
    try:
        async with engine.begin() as conn:
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            await conn.run_sync(Base.metadata.create_all)
        logger.info("startup_schema_ready", extra={"event": "startup"})
    except Exception:
        logger.exception("startup_schema_bootstrap_failed", extra={"event": "startup_error"})
    yield


app = FastAPI(
    title="Lenny Growth Assistant API",
    version="1.0.0",
    description="Grounded RAG assistant over Lenny's Podcast transcripts.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_id_and_timing(request: Request, call_next):
    request_id = str(uuid.uuid4())[:8]
    start = time.perf_counter()
    request.state.request_id = request_id
    try:
        response = await call_next(request)
    except Exception:
        logger.exception(
            "unhandled_exception",
            extra={"request_id": request_id, "event": "unhandled_exception"},
        )
        return JSONResponse(
            status_code=500,
            content={"error": "internal_error", "detail": "An unexpected error occurred.", "request_id": request_id},
        )
    duration_ms = round((time.perf_counter() - start) * 1000, 1)
    response.headers["X-Request-ID"] = request_id
    logger.info(
        "request_complete",
        extra={"request_id": request_id, "event": f"{request.method} {request.url.path} {response.status_code} {duration_ms}ms"},
    )
    return response


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    request_id = getattr(request.state, "request_id", "unknown")
    logger.exception("unhandled_exception_handler", extra={"request_id": request_id, "event": "exception"})
    return JSONResponse(
        status_code=500,
        content={"error": "internal_error", "detail": str(exc), "request_id": request_id},
    )


app.include_router(health.router)
app.include_router(sessions.router)
app.include_router(chat.router)


@app.get("/")
async def root():
    return {"service": "lenny-growth-assistant", "status": "running", "docs": "/docs"}
