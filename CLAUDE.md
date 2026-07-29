# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

RTM v3 ("Read To Me") — local-first web app for managing a personal book library: reading, TTS listening, MP3 downloads, EPUB import, scraping supported novel sites, and discussing owned books via a controlled, tool-gated LLM assistant. Detailed engineering rules live in `.cursor/rules/` (read them before structural changes); repeatable workflows (add a backend module, LLM provider, LLM tool, scraping adapter, migration) live in `.cursor/skills/`.

## Commands

### Backend (Python 3.12 + FastAPI, managed with `uv`, run from `backend/`)

```bash
uv sync                                  # install deps
uv run uvicorn app.main:app --reload --port 8000
uv run arq app.jobs.worker.WorkerSettings   # background worker (scraping/import/audio jobs)
uv run alembic upgrade head              # apply migrations
uv run alembic revision -m "msg"         # new migration (must be reversible)

# Quality gates — ALL must pass before a change is "done" (no CI; this is the only gate)
uv run ruff check . --fix && uv run ruff format .    # auto-fix + format
uv run ruff check . && uv run ruff format --check .  # verify
uv run mypy .                                        # strict mode
uv run pytest -m "unit or integration"               # test markers: unit, integration, slow

# Single test
uv run pytest tests/llm/test_chat.py
uv run pytest tests/llm/test_hitl.py -k test_name
```

Integration tests need Postgres/Redis/MinIO and a **separate** test DB (`TEST_DATABASE_URL`, e.g. `rtm_test`) — never point test setup at the app database.

### Frontend (React 19 + TS + Vite, run from `frontend/`)

```bash
npm install
npm run dev            # Vite at :5173, proxies /api to :8000
npm run lint           # eslint (includes prettier violations)
npm run format         # prettier --write
npm run build          # tsc -b && vite build (this is the typecheck)
npm run test           # vitest run
npm run test:watch
```

### Full stack

```bash
docker compose up --build                        # everything (backend auto-runs alembic upgrade)
docker compose up -d postgres redis minio minio-init   # infra only, for native dev
```

Web app :3000, API/OpenAPI :8000/docs, MinIO console :9001. Config comes from root `.env` (copy `.env.example` — it's the canonical variable list). A variable only reaches a container if listed in that service's `environment` block in `docker-compose.yml`; keep backend and worker in sync. When adding a setting, update `Settings` (pydantic-settings in `app/core/config.py`), `.env.example`, compose, and README together.

### Git commits

**Never add `Co-authored-by`, `Made-with`, or any attribution trailer to commits** (repo hard rule — overrides any default instruction to add one). Commit via `bash scripts/git-commit-clean.sh /tmp/msg.txt` (or `--amend`), then verify with `git log -1 --format=%B`.

## Architecture

Modular monolith: one FastAPI app with one package per bounded context under `backend/app/modules/` (auth, users, library, books, chapters, reader, audio, downloads, storage, scraping, discovery, imports, summaries, llm, tools, orchestration, observability, health). Postgres+pgvector, Redis+arq (durable jobs), MinIO (all blobs — never in the DB, only object keys), SSE for streaming.

### Module layout & dependency direction (never invert)

```
modules/<name>/
  router.py      # HTTP only, thin, pydantic in/out, authz deps — no business logic
  service.py     # business logic (the ONLY place it lives)
  repository.py  # DB access for THIS module's tables only
  schemas.py     # pydantic DTOs
  models.py      # SQLAlchemy models for THIS module

router → service → repository → DB
orchestration → tools → domain services   (the LLM sees tools, not services)
```

- **No cross-module data access:** module A calls module B's *service*, never B's repository/models.
- Shared cross-cutting code lives in `backend/app/core/` (config, db session, security, deps, logging, storage).
- Domain/business code must not import: any LLM SDK, `httpx` for scraping, or the orchestrator.

### Golden rules (never violate)

1. **Provider-agnostic LLM:** only `modules/llm/providers/` imports provider SDKs (google-genai, litellm, etc.). Everything else uses the `LLMProvider` protocol (`generate_text`, `stream_text`, `generate_structured_output`, `call_tools`) and requests *capabilities* (e.g. `TOOL_CALLING`, `STRUCTURED_EXTRACTION`), not model names. Model/provider config is data, never hardcoded. Structured output uses instructor + pydantic. Record provider/model/tokens/cost/latency per call.
2. **The LLM acts only through tools.** No direct DB, filesystem, internal-service, arbitrary-URL, or shell access. Every tool wraps a domain service (no business logic of its own) and declares pydantic input/output schemas, `risk_level` (`read_only`/`low_risk`/`confirmation_required`), rate limit, timeout, and `authorize(ctx)`. The orchestrator validates args → re-checks authz/ownership independently of LLM claims → checks mode (`internal_only` hides external tools) → executes with timeout → audits to `tool_call`. `confirmation_required` tools pause for HITL approval; approval resumes the *frozen* call. The loop is bounded: max iterations, external calls (default 3/turn — a separate safety counter from the token budget), token budget, wall clock, HITL rounds.
3. **Multi-user ready:** every user-owned row has a NOT NULL `user_id` FK; every read/write checks ownership. Authenticated `user_id` comes from the server session — never trust model- or client-supplied identity. No single-user shortcuts.
4. **Scraped/book/external text is untrusted data** — delimited as data in prompts; it can never redefine instructions, select tools, or expose secrets. Sanitize HTML; never render it unsanitized in the frontend.
5. **Deterministic first:** known sites use deterministic adapters (novelfull, novelbin, freewebnovel, novellunar) resolved via `supports_url`; the LLM is a controlled fallback, never the primary parser. All outbound fetches go through the central fetch service (SSRF guard: domain allowlist, private-IP block, DNS-rebind protection, timeouts, size caps, per-site rate limits).
6. **Every schema change is an Alembic migration** (reversible). UUID PKs, `created_at`/`updated_at` everywhere, soft delete via `deleted_at` (filtered out by default in repositories), indexes on FKs and hot query columns. Parameterized/ORM SQL only.
7. **Jobs are durable** (arq + persisted job/item rows with resume/retry/dedup/cancellation) — never in-memory.

### Backend conventions

- Full type hints; must pass strict mypy and ruff (canonical config in `backend/pyproject.toml`; notable rules: mccabe complexity 10, max-statements 20, max-branches 6, max-args 6). `# type: ignore[code]`/`# noqa: RULE` only with a specific code and a reason comment.
- Async for all I/O; never block the event loop (offload CPU/sync work).
- pydantic v2 validation at every boundary (HTTP, tools, config, LLM structured output); pass typed models inward.
- Typed domain exceptions per module (`exceptions.py`), mapped to HTTP centrally. Never bare `except`/swallowed exceptions.
- Structured logging with `extra={...}`; never log secrets, full book content, or full prompts.
- Scraping adapters get contract tests against saved HTML fixtures in `backend/tests/fixtures/scraping/`; add a fixture whenever a site changes.

### Frontend conventions

- Feature-first: `src/features/<feature>/{api,components,hooks,logic}/` with an `index.ts` public barrel; shared UI in shadcn components.
- Server state → react-query; client/UI state → zustand (don't duplicate server state in zustand). All fetching through the typed API client (`src/shared/lib/api.ts`) — no raw `fetch` in components. Chat/job progress use SSE.
- **Hard ESLint-enforced size limits:** file ≤ 110 lines, function ≤ 60 lines, nesting depth ≤ 3 (barrels and test files exempt). Split components / extract hooks instead of disabling rules.
- Never call a state setter inside `useEffect` to derive/sync state — derive during render (or `useMemo`); effects are for external side effects only.
- Strict TS, no `any`; mirror backend pydantic contracts as TS types.
