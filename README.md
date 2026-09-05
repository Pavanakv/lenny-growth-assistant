# The Lenny Growth Assistant

> **Take-home submission — Forward Deployed Engineer role.**
> Demo video: [add YouTube link here once recorded]
> Author: Pavana K V · [GitHub](https://github.com/Pavanakv) · [LinkedIn](https://linkedin.com/in/pavana-kv)

A full-stack, grounded RAG assistant over Lenny's Podcast transcripts:
ask product/growth questions with cited answers, generate Ship 30 for
30–style essays, and produce Markdown/HTML artifacts rendered in-app —
running entirely locally via Ollama, with an optional Anthropic Claude
cloud path.

See also: [`docs/PRD.md`](docs/PRD.md) · [`docs/architecture.md`](docs/architecture.md) · [`docs/design.md`](docs/design.md)

## Architecture at a glance

Next.js (chat + artifact viewer) → FastAPI → PostgreSQL + pgvector
│
├── Ollama (local, default)
└── Anthropic Claude (optional cloud)


Full diagram and schema: [`docs/architecture.md`](docs/architecture.md).

## Prerequisites

- Docker & Docker Compose v24+ (recommended path), **or** for running
  services individually: Python 3.11+, Node.js 20.x, PostgreSQL 16 with the
  `pgvector` extension, and [Ollama](https://ollama.com) installed locally.
- ~15 GB free disk (Ollama model weights + Postgres data).
- No cloud API key is required for the default demo.

## Quickstart (Docker Compose — recommended)

```bash
cp .env.example .env
docker compose up --build
```

This starts Postgres+pgvector, Ollama (auto-pulling `llama3.2:3b` and
`nomic-embed-text` on first boot — this can take a few minutes the first
time), the FastAPI backend on `:8000`, and the Next.js frontend on `:3000`.

Then, in a second terminal, run the one-time ingestion step against the
sample (or your own) transcripts:

```bash
docker compose exec backend python scripts/download_transcripts.py   # writes sample data if no --source given
docker compose exec backend python scripts/ingest.py
```

Open **http://localhost:3000**. Check **http://localhost:8000/api/health**
if anything looks off — it reports DB / Ollama / Anthropic / vector-index
status independently.

## Running services individually (no Docker)

**Database**
```bash
# Any local Postgres 16 with pgvector, or use docker for just the DB:
docker run -d --name lenny_pg -p 5432:5432 -e POSTGRES_PASSWORD=password123 \
  -e POSTGRES_DB=lenny_assistant pgvector/pgvector:pg16
```

**Ollama**
```bash
ollama serve &
ollama pull llama3.2:3b
ollama pull nomic-embed-text
```

**Backend**
```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp ../.env.example ../.env   # edit DATABASE_URL_LOCAL if needed
export DATABASE_URL=postgresql+asyncpg://postgres:password123@localhost:5432/lenny_assistant
uvicorn app.main:app --reload --port 8000
```

In another shell, ingest data:
```bash
cd backend
python scripts/download_transcripts.py
python scripts/ingest.py
```

**Frontend**
```bash
cd frontend
npm install
npm run dev
```

## Environment variables

See [`.env.example`](.env.example) for the full annotated list. The
essentials:

| Variable | Required | Default | Notes |
|---|---|---|---|
| `DATABASE_URL` | yes | points at the `db` compose service | asyncpg DSN |
| `DEFAULT_LLM_PROVIDER` | yes | `ollama` | `ollama` \| `anthropic` |
| `OLLAMA_BASE_URL` / `OLLAMA_CHAT_MODEL` / `OLLAMA_EMBED_MODEL` | yes (for the mandatory local demo) | see file | — |
| `ANTHROPIC_API_KEY` | no | empty | leave blank to run fully local; if `DEFAULT_LLM_PROVIDER=anthropic` and this is blank, the app falls back to Ollama and logs a warning |
| `RETRIEVAL_TOP_K` / `RETRIEVAL_SIMILARITY_THRESHOLD` | no | `5` / `0.35` | tune recall vs. precision |
| `NEXT_PUBLIC_API_URL` | yes (frontend) | `http://localhost:8000` | — |

Never commit a real `.env` — only `.env.example` is checked in.

## Local vs. cloud model

The **Ollama path is the mandatory demo path** and is the default with zero
configuration. The Anthropic path is fully wired (see
`app/providers/anthropic_provider.py` and `factory.py`) but optional — set
`ANTHROPIC_API_KEY` and either set `DEFAULT_LLM_PROVIDER=anthropic` or pick
"Claude (cloud)" in the UI toggle per session/request. If the key is missing,
the backend transparently serves Ollama and tells the frontend why (see the
`status` SSE event and the amber "using local model" notice).

## Tests

**Backend** (fast, zero external services — SQLite + mocked providers):
```bash
cd backend
pip install -r requirements.txt
pytest -v
```
Covers: session CRUD + validation (`test_api.py`), provider fallback logic +
artifact extraction + Ship 30 prompt construction (`test_providers.py`), and
transcript chunking edge cases (`test_retrieval.py`). Real pgvector
similarity search is exercised via the manual test plan below, since it
needs a live Postgres+pgvector instance.

**Frontend**
```bash
cd frontend
npx tsc --noEmit   # type-check
npm run build      # production build sanity check
```

### Manual UI test plan
1. Load `localhost:3000` with all services healthy → header shows "All
   systems ready"; composer is enabled.
2. Ask a question covered by the sample transcripts (e.g. *"How do I know if
   I've found product-market fit?"*) → answer streams, "N sources" appears,
   expanding it shows episode/guest/score.
3. Ask an out-of-domain question (e.g. *"What's the weather in Tokyo?"*) →
   answer states it lacks archive information; UI shows the amber "no
   sources" line.
4. Switch to **Ship 30 for 30 essay** mode, ask about growth loops → a
   long-form Markdown essay streams with headers/bold bullets/checklist.
5. Ask, in **Generate document** mode, for *"a one-page HTML landing page
   summarizing this"* → an artifact appears; the "View artifact" button
   opens the right panel; HTML renders inside the sandboxed iframe.
6. Toggle to **Claude (cloud)** without an API key set → send a message →
   amber status line explains the fallback to Ollama.
7. Stop the `ollama` container (`docker compose stop ollama`), send a
   message → a red error card appears in-chat (not a hung spinner);
   `/api/health` shows `ollama: down`.
8. Resize the window below `lg` breakpoint → chat pane goes full-width;
   artifact opens via the inline button.

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `/api/health` shows `database: down` | Postgres not up yet / wrong `DATABASE_URL` | `docker compose ps`, check `db` healthcheck; confirm `.env` matches compose service name |
| `/api/health` shows `ollama: down` | Ollama container still pulling models, or not running | `docker compose logs ollama`; first boot can take several minutes |
| Chat returns "insufficient information" for everything | Ingestion never ran, or threshold too high | `docker compose exec backend python scripts/ingest.py`; lower `RETRIEVAL_SIMILARITY_THRESHOLD` in `.env` |
| `ANTHROPIC_API_KEY` set but still using Ollama | Key not picked up | Confirm it's in `.env` (not just your shell), restart `backend` service |
| Frontend build fails on `dompurify` types | Missing devDependency | `npm install` again (types are pinned in `package.json`) |
| `pytest` errors on `transcript_chunks` table | Expected — that table needs real pgvector and is excluded from the SQLite test DB by design (see `tests/conftest.py`) | Not a bug; use the manual test plan for retrieval-specific checks |

## Deliverables checklist

| # | Deliverable | Location |
|---|---|---|
| 1 | Public GitHub repository | this repo |
| 2 | README.md | this file |
| 3 | PRD | [`docs/PRD.md`](docs/PRD.md) |
| 4 | design.md | [`docs/design.md`](docs/design.md) |
| 5 | architecture.md | [`docs/architecture.md`](docs/architecture.md) |
| 6 | Agent transcripts (incl. failed attempts) | [`agent_transcripts/`](agent_transcripts/) |
| 7 | Tests | [`backend/tests/`](backend/tests/) + manual UI test plan above |
| 8 | Demo video (2–3 min, camera on) | [add YouTube link here] |

## Known limitations & deviations from spec

Documented deliberately here rather than left for someone else to find:

- **Agent framework.** The brief allows the Anthropic Claude Agent SDK, Pi
  Coding Agent, or an equivalent. This submission uses a lightweight custom
  routing layer instead (`app/api/chat.py` + `app/providers/factory.py`),
  reasoned through in `docs/PRD.md` §1.3. Swapping in the Claude Agent SDK
  is a contained change scoped to that layer, not a rearchitecture.
- **Transcript corpus.** No official bulk transcript archive for Lenny's
  Podcast exists publicly. Ships with a small, clearly-labeled sample
  transcript set by default so the full pipeline is runnable end-to-end.
  Point `scripts/download_transcripts.py --source <your export>` at a real
  corpus, then `ingest.py --reset`, to use production data.
- **No database migration tool.** Schema is created via SQLAlchemy metadata
  at first connection, not Alembic — fine for this evaluation; migrations
  would be the next step before this touches a shared/production database.
- **Retrieval automated tests use SQLite + mocked embeddings**, not a live
  pgvector instance (see `tests/conftest.py` for why). Real vector-search
  behavior is covered by the manual UI test plan above, not by `pytest`.
  Automating that would need a disposable Postgres test container.

## Project structure

lenny-growth-assistant/
├── .env.example
├── docker-compose.yml
├── docs/{PRD,architecture,design}.md
├── agent_transcripts/
├── backend/
│ ├── app/{config,database,logging_config,main}.py
│ ├── app/models/{db_models,schemas}.py
│ ├── app/providers/{base,ollama_provider,anthropic_provider,factory}.py
│ ├── app/rag/{embeddings,retriever}.py
│ ├── app/skills/{ship30_writer,artifact_generator}.py
│ ├── app/api/{health,sessions,chat}.py
│ ├── scripts/{download_transcripts,ingest}.py
│ └── tests/
└── frontend/
└── src/{app,components/{Chat,Artifact},hooks,lib}


## Handoff notes for whoever runs this next

- Re-ingesting with a real transcript corpus: point
  `download_transcripts.py --source <your export>` at it, then
  `ingest.py --reset` to rebuild the index cleanly.
- Everything DB-schema-related lives in `app/models/db_models.py`; there's
  no separate migrations tool wired up (tables are created via SQLAlchemy
  metadata at first connection in this submission) — adding Alembic is the
  natural next step before this touches a shared/prod database.
- The provider factory (`app/providers/factory.py`) is the one place to add
  a third provider (e.g. OpenAI) later — implement `BaseLLMProvider` and
  register it there.