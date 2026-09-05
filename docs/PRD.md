# PRD — The Lenny Growth Assistant

## 1. Forward Deployment Brief

### 1.1 User and problem
**Primary user:** an early-to-mid career Product Manager or Growth lead (the
persona the client's product/growth team is building for) who wants tactical
answers to product/growth questions ("how do I find PMF", "how should I price
an early-stage SaaS product") grounded in real operator experience, without
listening to 200+ hours of podcast audio or trusting an ungrounded chatbot
that might hallucinate a tactic no guest ever said.

**Job to be done:** "When I have a specific product/growth decision in front
of me, I want a fast, trustworthy synthesis of what practitioners on Lenny's
Podcast actually said about it, with the option to turn that synthesis into a
polished, shareable essay — without needing to know what a model, a prompt,
or a vector database is."

**Pain removed:** hours of manual transcript search/skimming, uncertainty
about whether a generic LLM answer is grounded in real operator experience or
invented, and the extra step of manually reformatting a good answer into
something publishable.

### 1.2 Success metrics
Primary (product): **Grounded-answer rate ≥ 90%** — the share of non-trivial
questions where the assistant returns at least one transcript citation above
the similarity threshold, measured by dividing `sources.length > 0` responses
by total `/api/chat` calls in `mode=default`/`ship30` over a rolling week (a
simple SQL query against the `messages.sources` JSONB column; a dashboard is
future work, not in this submission's scope).

Secondary (operational): **Local-inference latency < 4s to first token** on
the mandatory Ollama demo path, measured as time from request start to the
first `event: token` SSE frame — this is what makes the local-only demo
feel usable rather than stalled.

Tertiary (safety): **0 unsandboxed-artifact incidents** — every HTML artifact
render goes through `SandboxedIframe` (DOMPurify + `sandbox="allow-scripts"`
without `allow-same-origin`); this is a binary pass/fail check in the manual
test plan (see `README.md`), not a percentage.

### 1.3 Assumptions
The brief was intentionally incomplete in several places; here is what I
assumed and why:

- **Transcript source.** There is no single official bulk-download of Lenny's
  Podcast transcripts. I assumed the client will supply (or license) a real
  transcript export, and built `scripts/download_transcripts.py` to accept
  three input modes: a local folder/zip of `.txt`/`.md`/`.json` files, a
  JSONL URL, or — when neither is available — a small set of clearly-labeled
  **sample** transcripts so the entire pipeline (ingest → retrieve → answer →
  cite) is runnable and testable end-to-end without a data-licensing
  dependency blocking the evaluation.
- **Agent framework.** The brief allows "Anthropic Claude Agent SDK or Pi
  Coding Agent." I implemented a lightweight custom agent/routing layer
  instead of adopting either SDK wholesale, because the assignment's actual
  requirements (provider-swappable chat + a retrieval tool + two "skills") are
  fully expressible as a thin FastAPI service, and a hand-rolled layer is
  easier for an evaluator to read top-to-bottom in one sitting than tracing
  through a third-party agent framework's internals. This is a documented
  scope trade-off, not an oversight — see 1.5.
- **Auth.** No login/multi-tenant auth is implemented. Sessions are
  identified by an unguessable UUID only. Acceptable for an internal
  single-team tool per the brief; flagged as a gap for production in 1.5.
- **Embedding model.** Anthropic has no embeddings API, so retrieval always
  embeds via the local Ollama `nomic-embed-text` model regardless of which
  provider answers the chat turn (documented in `architecture.md`).
- **Single embedding dimensionality.** The `transcript_chunks.embedding`
  column is fixed at 384 dims; provider embeddings are pooled/padded to fit
  (see `app/providers/ollama_provider.py::_fit_dim`) so the schema doesn't
  need to change if the embedding backend changes later.

### 1.4 Scope choices

**Included**
- FastAPI backend, PostgreSQL + pgvector persistence, session/message/
  artifact schema, structured logging, typed error responses, health probe.
- Ollama (mandatory, default) and Anthropic (optional cloud) chat providers
  behind one interface, switchable per-session or per-request, with
  transparent fallback when Anthropic has no key.
- RAG ingestion (chunk → embed → store) and threshold-gated retrieval with
  source citation.
- Two skills: grounded Q&A with follow-up context, and the Ship 30 for 30
  essay generator, plus a general-purpose Markdown/HTML artifact generator.
- Next.js chat UI with a Claude-Artifacts-style side panel, sandboxed HTML
  rendering, and a visible model-provider toggle.
- Docker Compose one-command startup, `.env.example`, automated tests, a
  manual UI test plan, and this documentation set.

**Explicitly excluded (with reasoning)**
- **Authentication/multi-tenancy** — out of scope for an internal single-team
  evaluation tool; the schema's `session.user_metadata` JSONB column is a
  ready extension point.
- **Streaming token-level cost/usage tracking** — logged per-request in
  structured logs, but not aggregated into a billing dashboard.
- **Automatic transcript re-crawling/refresh scheduler** — `ingest.py` is
  idempotent and re-runnable, but there's no cron/webhook wiring in this
  submission; noted as a "Day 2" operational task in the README.
- **A real production-scale transcript corpus** — see 1.3; the pipeline is
  built to scale (pgvector HNSW index, batched chunking) but is only
  exercised against sample data here for reproducibility without a data
  license.
- **Fine-grained RBAC on artifacts** — any holder of a session ID can see
  that session's artifacts; acceptable for the stated use case.

### 1.5 Risks and trade-offs
| Risk | Mitigation in this build | Residual risk |
|---|---|---|
| **Hallucination** | System prompt forces "I don't have enough information..." when no chunk clears the similarity threshold; UI shows an explicit "0 sources" warning badge. | A model can still ignore instructions under adversarial prompting; no output-side fact-checker is implemented. |
| **Local-model quality** | Ollama 3B model is small; grounded answers can be shallower/less fluent than the cloud model. | Documented, not solved — the toggle exists precisely so an evaluator can compare. |
| **Latency** | Streaming SSE gives perceived responsiveness even when total generation is slow. | Cold-start Ollama model load on first request can exceed the 4s target; `docker-compose.yml` pre-pulls the model at container start to reduce this. |
| **Data leakage** | HTML artifacts are sandboxed (no `allow-same-origin`, no external script execution, DOMPurify strip); Anthropic calls only leave the machine when explicitly selected and a key is configured. | The Anthropic provider does send the retrieved transcript context and user message to a third party by design when selected — this is inherent to using a cloud LLM at all, and is called out in the UI's provider badge. |
| **Unsafe artifact rendering** | Sandbboxed iframe + DOMPurify allow-list, `srcDoc` (not `src`), forbidden tags/attrs. | A sufficiently creative script inside the sandbox could still, e.g., open a popup or consume CPU (denial-of-service on the tab); acceptable residual risk for an internal tool, called out in `architecture.md`. |
| **Cost (cloud path)** | Off by default; requires an explicit API key. | None additional once opted in — standard Anthropic API pricing applies. |

## 2. Flows
1. **New session:** frontend calls `POST /api/sessions` on load → gets a
   session UUID → all chat turns reference it.
2. **Grounded question:** user types a question in "Ask" mode → backend
   embeds the query → retrieves top-K chunks above the threshold → streams a
   cited answer → frontend renders inline citations and an "0 sources"
   warning if the archive didn't support the question.
3. **Ship 30 for 30 essay:** user switches to that mode → same retrieval step
   → the Ship 30 skill prompt (not the default Q&A prompt) is used → a
   ~1,250-word essay streams back.
4. **Artifact generation:** user asks for a document/HTML snippet → the model
   emits an `<artifact>` block → backend extracts, persists, and returns it
   separately from the chat reply → frontend opens the Artifact Viewer panel.
5. **Provider switch:** user toggles Ollama/Claude → next turn uses that
   provider; if Claude has no key configured, the backend serves Ollama and
   emits a `status` SSE event explaining the fallback.

## 3. Acceptance criteria
- [ ] A fresh `docker-compose up` (with `ollama pull` completing) serves a
      working chat UI at `localhost:3000` with zero manual DB setup.
- [ ] Asking a question covered by the ingested sample transcripts returns an
      answer with ≥1 cited source.
- [ ] Asking an out-of-domain question returns the "I don't have enough
      information..." response and an explicit 0-sources UI state.
- [ ] Switching to "Ship 30 for 30 essay" mode produces a ~1,000–1,400 word
      Markdown essay with headers, bold-anchored bullets, and a closing
      checklist.
- [ ] Requesting a document produces an artifact that renders in the side
      panel (Markdown via `react-markdown`, HTML via the sandboxed iframe).
- [ ] `/api/health` reports each dependency (DB, Ollama, Anthropic,
      vector index) independently.
- [ ] `pytest` passes with zero external services running (SQLite-backed unit
      tests + mocked providers).
- [ ] Stopping the `ollama` container mid-session produces a visible SSE
      error in the chat, not a hung UI or an unhandled 500.

## 4. Implementation plan (as executed)
1. Discovery docs (this PRD + architecture.md + design.md) written first to
   fix scope before code.
2. Backend: config → DB models → providers → RAG → skills → API routes →
   main.py wiring → tests, validated by running `pytest` locally (SQLite) at
   each stage.
3. Frontend: config → API client → SSE hook → chat components → artifact
   viewer → page composition, validated with `tsc --noEmit` and `next build`.
4. Deployment: Dockerfiles, `docker-compose.yml`, `.env.example`.
5. Documentation + agent transcripts assembled last, reflecting what was
   actually built (not aspirational).
