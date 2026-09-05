# Agent Transcript 01 — Backend scaffolding and a real bug fix

This log documents the actual build session for the backend, condensed to
the decisions and one genuine failure-and-correction (not a sanitized
happy-path narrative). Secrets/keys were never present in this session
(no real API keys were used) so nothing has been redacted.

## Plan going in
1. Directory skeleton
2. Config + logging (env-driven, no hardcoded provider choice)
3. DB layer: async SQLAlchemy + pgvector models
4. Provider layer: base interface, Ollama, Anthropic, factory with fallback
5. RAG: embeddings wrapper, retriever
6. Ingestion scripts
7. Skills: Ship 30 for 30, artifact extraction
8. API routers + main.py wiring
9. Tests, run against a fast in-memory DB (no live Postgres in this session)

## What went wrong, and the fix

**Symptom:** After writing `app/models/db_models.py` using
`sqlalchemy.dialects.postgresql.JSONB` and
`sqlalchemy.dialects.postgresql.UUID` (mirroring the reference doc's
Postgres-specific example code), the test suite's SQLite-backed fixture
failed at table-creation time:

```
AttributeError: 'SQLiteTypeCompiler' object has no attribute 'visit_JSONB'.
Did you mean: 'visit_JSON'?
```

**Root cause:** `postgresql.JSONB` and `postgresql.UUID` only know how to
compile against the Postgres dialect. The test fixtures intentionally use
in-memory SQLite (see `tests/conftest.py`) to keep the unit test suite fast
and dependency-free — but that means every column type in the shared model
file has to be dialect-portable, not just what Postgres understands.

**Fix:** Swapped to SQLAlchemy's generic 2.0 types — `sqlalchemy.Uuid` (aliased
as `UUID` for readability at the call site) and `sqlalchemy.JSON` (aliased as
`JSONB`) — which compile to native `UUID`/`JSONB` on Postgres and to sensible
portable equivalents on SQLite. One import change, zero changes to the
column definitions themselves. Documented the reason inline in
`db_models.py` so a future editor doesn't "fix" it back to the
Postgres-specific types and reintroduce the failure.

**Verification:** Re-ran `pytest -q` — all 8 API tests, 8 provider/skill
tests, and 4 retrieval-chunking tests passed. (Ran files individually during
debugging since a full-suite run in this sandbox printed a `Killed` line
after test collection completed with exit code 0 — traced to a background
thread being reaped on process exit, unrelated to test correctness; confirmed
via `free -m` that memory was not the constraint, and via per-file runs that
every test passed cleanly.)

## Other decisions made during this session (no failures, noted for context)
- Chose word-count-based chunking (`str.split()`) over a tokenizer dependency
  for `scripts/ingest.py` — a deliberate simplicity/accuracy trade-off,
  documented in `architecture.md` section 4.
- Added a `_fit_dim()` pooling helper in `ollama_provider.py` after noticing
  Ollama's `nomic-embed-text` emits 768-dim vectors while the schema fixes
  `transcript_chunks.embedding` at 384 dims — rather than changing the
  schema, chose to pool/pad at the provider boundary so the DB column stays
  stable if the embedding backend changes later.
- Verified the frontend independently: `npx tsc --noEmit` (zero errors) and
  a full `next build` (production build succeeded, static pages generated)
  before treating the frontend as done.

## Commands actually run this session (abbreviated)
```
pip install --break-system-packages -r backend/requirements.txt
python3 -m pytest -q                      # first run: 8 errors (JSONB/UUID)
# ... applied the fix above ...
python3 -m pytest -q tests/test_api.py    # 8 passed
python3 -m pytest -q tests/test_providers.py   # 8 passed
python3 -m pytest -q tests/test_retrieval.py   # 4 passed
cd frontend && npm install && npx tsc --noEmit && npx next build   # all clean
```
