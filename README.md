# RTM v3 — Read To Me

Local-first web platform to manage, read, listen to, download, import, scrape, search,
summarize, and discuss books through a React GUI and a controlled LLM assistant.

See `docs/assistant-capabilities.md` for current assistant behavior and
`docs/llm-planning/README.md` for architecture and remaining work.

## Stack

- **Backend:** Python 3.12 + FastAPI (`backend/`)
- **Frontend:** React 19 + TypeScript + Vite (`frontend/`)
- **Infra:** PostgreSQL + pgvector, Redis, MinIO (via Docker Compose)

## Quick start (Docker)

```bash
cp .env.example .env
docker compose up --build
```

- App: http://localhost:3000 (redirects to login → library)
- API docs: http://localhost:8000/docs
- Health: http://localhost:8000/api/health
- MinIO console: http://localhost:9001 (`rtm` / `rtmsecret`)

Default login (from `.env`): **admin** / **changeme123**

After login:

- `/library` manages books and chapters.
- `/read/...` provides browser/server TTS with progress and highlighting.
- `/scraper` runs site scrapes and EPUB imports.
- The app-wide assistant can search and discuss owned books, play/resume chapters,
  create monitored audio downloads, update reversible UI settings, and discover/import
  titles through validated tools.

## Assistant setup

The assistant is disabled by default. Add a Gemini key and enable it in `.env`:

```dotenv
LLM_ENABLED=true
GEMINI_API_KEY=...
LLM_ASSISTANT_MODE=internal_only
```

Use `external_allowed` only when discovery/scraping tools should be available. External
and expensive actions still require a structured confirmation form.

Important defaults:

- True provider-token streaming over SSE, with Stop to cancel a turn.
- Live status while tools run; the chat sticks to the bottom unless you scroll up.
- 64K cumulative input-token budget per turn. Tool rounds enforce the cap; a completed
  final answer may record soft-limit overage instead of being discarded.
- Rolling summaries keep older conversation context while preserving full messages.
- SAPI/Zira audio downloads default to Microsoft Zira Desktop at 1.35×.
- Confirmed range downloads show in-chat progress and auto-download when ready.
- Generated MP3 names include the book title, chapter range, and a short unique suffix.
- Download jobs/objects expire after `DOWNLOAD_JOB_TTL_HOURS` (default 24); arq purges
  expired rows twice an hour.

## Local development

### Infra only

```bash
docker compose up postgres redis minio minio-init
```

### Backend

```bash
cd backend
uv sync
uv run uvicorn app.main:app --reload --port 8000
```

Lint / types / tests (must pass before considering work done):

```bash
uv run ruff check . --fix && uv run ruff format .
uv run ruff check . && uv run ruff format --check .
uv run mypy .
uv run pytest -m "unit or integration"
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Opens http://localhost:5173 (Vite proxies `/api` → backend `:8000`).

```bash
npm run lint
npm run format
npm run build
npm run test
```

## Milestones

| Milestone | Goal |
|-----------|------|
| **A** | v2 parity (library, reader, TTS, scraping) + chat UI placeholder + UI redesign (shadcn, dark mode) |
| **B** | Tool-using assistant, true streaming, form HITL, playback/download/settings actions — complete |
| **C** | Discovery/import and persisted summaries shipped; theme discovery and richer grounded discussion remain |

## Repo layout

```
backend/          FastAPI modular monolith
frontend/         React SPA
docs/             Phase 0 plan + ADRs
.cursor/rules/    Always-on conventions
.cursor/skills/   Repeatable workflows
docker-compose.yml
```
