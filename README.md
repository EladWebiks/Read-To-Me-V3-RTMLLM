# RTM v3 — Read To Me

Local-first web platform to manage, read, listen to, scrape, and (later) discuss books.

See `docs/phase-0-discovery.md` for architecture and milestones.

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

After login you can manage books/chapters at `/library`.

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
| **B** | Basic LLM assistant (tools over library/reader) |
| **C** | Full conversational scrape/play/discuss (+ discovery) |

## Repo layout

```
backend/          FastAPI modular monolith
frontend/         React SPA
docs/             Phase 0 plan + ADRs
.cursor/rules/    Always-on conventions
.cursor/skills/   Repeatable workflows
docker-compose.yml
```
