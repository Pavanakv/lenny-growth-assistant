# Architecture

## 1. System overview

```
                         ┌──────────────────────────┐
                         │        Frontend           │
                         │   Next.js 14 (App Router) │
                         │  ChatPane │ ArtifactViewer │
                         └────────────┬──────────────┘
                                      │ REST + SSE (fetch, streaming)
                                      ▼
                         ┌──────────────────────────┐
                         │         Backend           │
                         │        FastAPI            │
                         │ ┌──────────┐ ┌──────────┐ │
                         │ │ sessions │ │   chat   │ │
                         │ │  router  │ │  router  │ │
                         │ └──────────┘ └────┬─────┘ │
                         │                    │       │
                         │     ┌──────────────┼─────┐ │
                         │     ▼              ▼     ▼ │
                         │ Retriever    Skills   Provider │
                         │ (pgvector)  (ship30,   Factory │
                         │             artifact)          │
                         └──┬─────────────┬───────┬──────┘
                            │             │       │
                 ┌──────────▼───┐   ┌─────▼───┐  ┌▼─────────────┐
                 │  PostgreSQL   │   │ Ollama  │  │  Anthropic    │
                 │  + pgvector   │   │ (local, │  │  API (cloud,  │
                 │               │   │ default)│  │  optional)    │
                 └───────────────┘   └─────────┘  └───────────────┘
```

## 2. Database schema

| Table | Purpose | Key columns |
|---|---|---|
| `sessions` | one row per chat session | `id (uuid, pk)`, `title`, `llm_provider`, `user_metadata (jsonb)`, `created_at`, `updated_at` |
| `messages` | one row per chat turn | `id (uuid, pk)`, `session_id (fk)`, `role`, `content`, `mode`, `provider`, `sources (jsonb)`, `created_at` |
| `artifacts` | generated documents | `id (uuid, pk)`, `message_id (fk)`, `artifact_type`, `title`, `content`, `created_at` |
| `transcript_chunks` | ingested, embedded transcript pieces | `id (uuid, pk)`, `episode_title`, `guest_name`, `source_path`, `chunk_index`, `chunk_text`, `timestamp_ref`, `embedding (vector(384))` |

`transcript_chunks.embedding` has an HNSW index (`vector_cosine_ops`) for
approximate-nearest-neighbor cosine search at scale; see
`app/models/db_models.py`.

Models use SQLAlchemy's generic `Uuid`/`JSON` types (not
`postgresql.UUID`/`JSONB` directly) so the same model file backs both
production Postgres and the in-memory SQLite database used by the unit test
suite — this is the one deliberate portability shim in the schema.

## 3. API endpoints

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/health` | Independent status of DB, Ollama, Anthropic, vector index |
| `POST` | `/api/sessions` | Create a session |
| `GET` | `/api/sessions` | List recent sessions |
| `GET` | `/api/sessions/{id}` | Fetch a session + its message history |
| `DELETE` | `/api/sessions/{id}` | Delete a session (cascades to messages/artifacts) |
| `POST` | `/api/chat` | Streaming (SSE) chat turn — see below |

### `/api/chat` request/response contract
Request:
```json
{ "session_id": "uuid", "message": "string", "mode": "default|ship30|artifact", "provider": "ollama|anthropic|null" }
```
SSE event stream:
```
event: status   data: {"message": "Retrieving transcripts..."}
event: token    data: {"content": "partial text"}
event: error    data: {"message": "..."}                # terminal, stream ends
event: done     data: {"message_id", "sources", "artifact", "provider"}  # terminal
```
Validation: `message` is required, 1–8000 chars (Pydantic `Field`), a missing
`session_id` returns `404`, and any unhandled exception is caught by the
global handler in `main.py` and returned as a structured
`{error, detail, request_id}` JSON body — never a raw traceback.

## 4. Ingestion / retrieval flow

1. `scripts/download_transcripts.py` populates `backend/data/transcripts/`
   (local dir/zip, a JSONL URL, or clearly-labeled sample data — see PRD 1.3).
2. `scripts/ingest.py`:
   - Loads each file, recursive word-based chunking
     (`CHUNK_TOKEN_SIZE`≈650 words, `CHUNK_TOKEN_OVERLAP`≈100 words — word
     count is used as a lightweight proxy for tokens to avoid a tokenizer
     dependency; documented as an approximation).
   - Embeds each chunk via the active embedding provider (always Ollama —
     see PRD 1.3).
   - Upserts into `transcript_chunks`, preserving `source_path` +
     `chunk_index` for traceability back to the original file.
   - Idempotent by default (skips already-ingested `source_path`s); `--reset`
     wipes and reloads.
3. `TranscriptRetriever.retrieve()` embeds the incoming query, runs a
   pgvector cosine-distance `ORDER BY ... LIMIT` query, and filters to chunks
   with `similarity_score >= RETRIEVAL_SIMILARITY_THRESHOLD`. An empty result
   is a first-class outcome the caller (`chat.py`) must handle, not an error.

## 5. Agent routing / skills

`app/api/chat.py` is the router: based on `mode`, it selects one of two
system prompts:
- **`default`/`artifact`** → `DEFAULT_SYSTEM_PROMPT` (+ `ARTIFACT_SYSTEM_PROMPT`
  appended so the model may emit an `<artifact>` block when asked for a
  document).
- **`ship30`** → `SHIP30_SYSTEM_PROMPT` from `app/skills/ship30_writer.py`,
  a dedicated, structured prompt encoding the Ship 30 for 30 rules (hook,
  length, formatting, grounding, checklist ending) rather than an ad hoc
  one-off instruction.

After generation, `app/skills/artifact_generator.py::extract_artifact()`
regex-parses any `<artifact type="..." title="...">...</artifact>` block out
of the raw model output, so the chat transcript never shows raw artifact
markup and the artifact is persisted/returned as a separate structured
object.

## 6. Model routing / provider toggle

`app/providers/factory.py::get_provider()` resolves, per request:
`explicit request field` → `session.llm_provider` → `DEFAULT_LLM_PROVIDER`.
If Anthropic is chosen without `ANTHROPIC_API_KEY` set, it **silently
substitutes Ollama** and the response stream carries a `status` event telling
the frontend to show a "using local model" notice — this is the documented
fallback behavior. Embeddings always go through Ollama's `nomic-embed-text`
regardless of chat provider (Anthropic has no embeddings endpoint).

## 7. Artifact rendering security

Untrusted model output is never rendered as live HTML in the parent page.
`SandboxedIframe` (frontend):
- Sanitizes with DOMPurify (`WHOLE_DOCUMENT`, forbids `<form>`, `<iframe>`,
  `<object>`, `<embed>`, and inline event-handler attributes).
- Mounts via `srcDoc` (never a fetchable `src` URL).
- `sandbox="allow-scripts"` **without** `allow-same-origin` — the browser
  treats the frame as opaque cross-origin, so any script inside it cannot
  read/write the parent's cookies, `localStorage`, or DOM, and cannot
  navigate the top-level window.

What the viewer explicitly **permits**: inline `<style>`, inline `<script>`
that only affects the frame's own DOM (e.g. a small interactive demo).
What it **blocks**: forms, nested iframes/objects/embeds, inline event
handlers, parent-page access, top-level navigation.

## 8. Deployment topology

`docker-compose.yml` runs four services: `db` (Postgres 16 + pgvector),
`ollama` (pulls `llama3.2:3b` + `nomic-embed-text` on first boot),
`backend` (FastAPI on :8000), `frontend` (Next.js standalone build on :3000).
`backend` depends on `db`'s healthcheck; ingestion is a separate manual step
(`docker compose exec backend python scripts/ingest.py`) rather than
baked into the image build, so re-ingesting with a new corpus doesn't require
a rebuild.

## 9. Observability & resilience

- Structured single-line logs (`app/logging_config.py`) with `request_id`,
  `session_id`, `provider`, `event` fields — greppable, aggregator-agnostic.
- A request-id middleware (`main.py`) tags every request/response pair and
  turns any unhandled exception into a structured JSON error instead of a
  bare 500/traceback leak.
- `/api/health` checks DB, Ollama, Anthropic, and the vector index
  **independently** so a partial outage is diagnosable at a glance.
- Explicit failure handling: missing Ollama → `ProviderUnavailableError` →
  SSE `error` event (not a hung stream); missing Anthropic key → fallback,
  not failure; empty retrieval → explicit "insufficient context" answer, not
  a hallucinated one; DB unreachable at startup → app still boots, `/health`
  reports `down` rather than crash-looping the container.
