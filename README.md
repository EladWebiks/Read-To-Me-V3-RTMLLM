# RTM v3 — Read To Me

Read To Me is a local-first web application for building a personal book library,
reading in the browser, listening with text-to-speech (TTS), producing MP3 downloads,
importing EPUB files, scraping supported novel sites, and discussing owned books with
a controlled LLM assistant.

The project is a from-scratch v3 rebuild. It keeps the useful reading and scraping
workflows from RTM v2 while replacing its in-memory jobs and single-purpose backend
with durable storage, background workers, ownership checks, and a tool-gated assistant.

> **Project status:** Milestones A and B are implemented. Milestone C currently includes
> title discovery/import and persisted book summaries. The next discovery slice is a
> batched theme/trope recommendation tool so “find three books like this” uses one
> bounded external operation instead of repeated title searches. Richer multi-step book
> discussion, destructive/large assistant tools, and the evaluation harness also remain.

## Contents

- [What RTM can do](#what-rtm-can-do)
- [System architecture](#system-architecture)
- [LLM architecture and safety](#llm-architecture-and-safety)
- [Prerequisites](#prerequisites)
- [Quick start with Docker](#quick-start-with-docker)
- [Get and configure a Gemini API key](#get-and-configure-a-gemini-api-key)
- [Local development](#local-development)
- [Configuration](#configuration)
- [Repository structure](#repository-structure)
- [Engineering rules](#engineering-rules)
- [Testing and quality gates](#testing-and-quality-gates)
- [Troubleshooting](#troubleshooting)
- [Further documentation](#further-documentation)

## What RTM can do

### Library and reader

- Create and manage an owned book library and its chapters.
- Read chapters in a responsive reader with dark mode and configurable typography.
- Save chapter and word/paragraph reading progress.
- Search book metadata, stored summaries, and chapter content.
- Continue from the last saved reading position.

### Text-to-speech and downloads

- Use browser speech or server-side TTS.
- Use Edge neural voices or the local SAPI-compatible provider.
- Highlight the current word or paragraph while reading.
- Autoplay the next chapter and resume playback through assistant actions.
- Generate a single-chapter MP3 immediately.
- Generate chapter-range MP3 jobs through a confirmation form.
- Track generation progress in chat and automatically download completed audio.
- Store generated files in MinIO and expose them through expiring signed URLs.
- Purge expired download rows and objects after `DOWNLOAD_JOB_TTL_HOURS` (24 by
  default).

SAPI downloads default to Microsoft Zira Desktop at 1.35× when no other voice/rate is
selected. Generated filenames include the book title, chapter range, and a short job
suffix.

### Import, scraping, and discovery

- Preview and import EPUB files using bounded, chunked background work.
- Scrape supported sites with deterministic per-site adapters:
  - `novelfull.net`
  - `novelbin.com`
  - `freewebnovel.com`
  - `novellunar.com`
- Run durable scrape jobs with progress, retries, cancellation, and ownership checks.
- Search supported sources by title/alias, rank matching sources, and confirm an import
  without manually pasting a URL.

Scraped pages and book text are always treated as untrusted data, never as instructions
for the assistant.

**Current discovery limitation:** discovery accepts one title/alias per tool call; it
does not yet search reliably by theme, trope, or similarity. A recommendation prompt
may cause the model to verify several guessed titles separately and hit the default
three-external-call turn budget. Increasing the token budget does not help because this
is a separate safety counter. The planned fix is a bounded batch recommendation tool
that accepts a seed book/themes and optional candidate titles, searches deterministic
sources inside one discovery operation, excludes owned books, deduplicates/ranks the
results, and returns evidence for up to the requested count. The external-call cap stays
small instead of being raised to conceal inefficient tool use.

### Controlled assistant

The app-wide assistant can:

- Search the user's library and retrieve book/chapter details.
- Read or create persisted, content-hash-invalidated book summaries.
- Answer grounded questions from owned content.
- Find reading progress and recently read chapters.
- Navigate to and play/resume a chapter.
- Create and monitor audio downloads.
- Change allowlisted, reversible UI/TTS settings.
- Discover titles and propose a ranked import.
- Start scraping/import work only after explicit human confirmation.

The chat streams real provider output over Server-Sent Events (SSE), exposes live tool
status, supports cancellation, and keeps long conversations usable with rolling
summaries. See [`docs/assistant-capabilities.md`](docs/assistant-capabilities.md) for
working prompts and the exact current tool set.

## System architecture

RTM runs as a modular monolith: one FastAPI application contains bounded-context
modules, while PostgreSQL, Redis, MinIO, an arq worker, and the React SPA run as
separate services.

```mermaid
flowchart LR
    User[Browser] --> Web[React 19 SPA<br/>Vite + Tailwind]
    Web -->|REST + SSE| API[FastAPI modular monolith]

    API --> PG[(PostgreSQL 16<br/>pgvector)]
    API --> Redis[(Redis 7)]
    API --> MinIO[(MinIO object storage)]
    API -->|provider abstraction| Gemini[Gemini API]

    Redis --> Worker[arq worker]
    Worker --> PG
    Worker --> MinIO
    Worker --> Sources[Supported novel sites]
    Worker --> TTS[Edge / SAPI TTS]

    MinIO -->|signed expiring URL| User
```

### Service responsibilities

- **Frontend (`frontend/`)** — React Router SPA, reader/player, assistant shell,
  scraper/import UI, React Query server state, and Zustand client preferences.
- **Backend (`backend/`)** — HTTP/SSE boundaries, domain services, authorization,
  persistence, LLM orchestration, tool execution, and job creation.
- **PostgreSQL + pgvector** — users, books, chapters, progress, conversations, audit
  records, jobs, summaries, and LLM telemetry. Vector support is available, but RAG is
  intentionally deferred until measured retrieval quality requires it.
- **Redis + arq** — durable queue coordination for scraping, EPUB import, downloads,
  and scheduled cleanup.
- **MinIO** — EPUB chunks and generated audio objects; clients receive signed,
  short-lived download URLs rather than direct object access.

### Backend dependency direction

Business logic lives in services. Modules may call another module's public service, but
must never reach into another module's repository or SQLAlchemy models.

```mermaid
flowchart LR
    Router[router.py<br/>HTTP only] --> Service[service.py<br/>business logic]
    Service --> Repository[repository.py<br/>module-owned data]
    Repository --> DB[(PostgreSQL)]

    Orchestrator[orchestration] --> Tools[validated tools]
    Tools --> Service
    Orchestrator --> LLM[LLMProvider abstraction]
```

## LLM architecture and safety

The model does not have direct access to PostgreSQL, Redis, MinIO, the filesystem,
arbitrary websites, internal services, or a shell. It can only propose calls to a
registered tool. The backend validates, authorizes, rate-limits, audits, and executes
that proposal.

### Assistant request flow

```mermaid
sequenceDiagram
    actor User
    participant UI as React assistant
    participant Chat as FastAPI chat/SSE
    participant Orch as Orchestrator
    participant LLM as LLMProvider (Gemini)
    participant Tool as Tool registry/executor
    participant Domain as Domain service
    participant DB as PostgreSQL

    User->>UI: Send message
    UI->>Chat: POST message + safe route context
    Chat->>Orch: Start bounded turn
    Orch->>DB: Persist user message
    Orch->>LLM: Stream messages + allowed tool schemas
    LLM-->>Orch: Text deltas and/or tool proposal

    alt Read-only or low-risk tool
        Orch->>Tool: Validate + authorize + execute
        Tool->>Domain: Call public service
        Domain->>DB: Ownership-scoped read/write
        Tool-->>Orch: Validated structured result
    else Confirmation-required tool
        Orch-->>UI: SSE confirmation form; pause
        User->>UI: Approve/edit or reject
        UI->>Chat: POST confirmation
        Chat->>Orch: Resume frozen call
        Orch->>Tool: Revalidate + authorize + execute
        Tool->>Domain: Call public service
    end

    Orch->>DB: Audit tool call and LLM usage
    Orch-->>UI: Real SSE text/status/result events
```

### Core controls

- **Provider abstraction:** domain code depends on capabilities such as tool calling,
  never on Gemini model names or Google SDK types.
- **Tool-only actions:** every model-triggered action has pydantic input/output schemas,
  a risk level, authorization, audit, timeout, and rate limit.
- **Ownership:** authenticated `user_id` comes from the server session. Model- or
  client-supplied identity is never trusted.
- **Assistant modes:** `internal_only` hides tools that touch external sites;
  `external_allowed` exposes them but does not bypass confirmation.
- **Human in the loop (HITL):** external, expensive, large, import, or destructive work
  pauses the turn and presents a structured form. Approval resumes the frozen call;
  it does not let the model invent a replacement action.
- **Bounded orchestration:** iteration, external-call, input-token, output-token,
  retry, wall-clock, and HITL-round limits prevent uncontrolled loops.
- **Context management:** recent messages remain verbatim and older context is captured
  in rolling summaries. Tool rounds enforce a 64K cumulative input-token budget; a
  completed final answer may record a soft overage rather than being discarded.
- **Observability:** LLM executions, costs, tool calls, confirmation outcomes, and run
  IDs are persisted in PostgreSQL. Langfuse integration is optional and disabled.
- **Prompt-injection boundary:** book, scraped, tool, and route-context text is
  delimited as data and cannot select tools, alter policy, or approve actions.

## Prerequisites

### Recommended: Docker workflow

Install:

1. **Git**
2. **Docker Desktop** (or Docker Engine + Compose v2)
3. At least **4 GB of free RAM** for the full local stack
4. Free host ports `3000`, `8000`, `5432`, `6379`, `9000`, and `9001`, or change them
   in `.env`

On Windows, enable the WSL 2 backend in Docker Desktop. Commands below work in Git Bash,
WSL, macOS, and Linux shells. PowerShell users can replace `cp` with `Copy-Item`.

### Native development

If running application processes outside Docker, also install:

- **Python 3.12**
- **uv** — <https://docs.astral.sh/uv/getting-started/installation/>
- **Node.js 20.19+ or 22.12+** and npm (required by Vite 7)
- **ffmpeg** on `PATH` for server-side audio conversion and chapter merging

PostgreSQL, Redis, and MinIO can still run in Docker while the backend/frontend run
natively.

## Quick start with Docker

### 1. Clone and configure

```bash
git clone https://github.com/EladWebiks/Read-To-Me-V3-RTMLLM.git
cd Read-To-Me-V3-RTMLLM
cp .env.example .env
```

The development defaults work without an LLM key. Before exposing this stack outside
your machine, change `JWT_SECRET` and all database/MinIO credentials. `ADMIN_PASSWORD`
is a legacy seed-only value: it is hashed into a column that nothing verifies any more,
because Google SSO is the only way to sign in. Never commit `.env`; it is ignored by Git.

### 2. Create a Google OAuth client (required to sign in)

Google SSO is the only sign-in method, so this step is not optional: with
`GOOGLE_CLIENT_ID` unset the login endpoints return **503** and nobody can get in.

1. In the [Google Cloud console](https://console.cloud.google.com/), select or create a
   project, then open **APIs & Services → Credentials**.
2. Configure the OAuth consent screen if prompted (External, testing mode is fine), and
   add your own Google account as a test user.
3. **Create credentials → OAuth client ID → Web application**.
4. Add both of these as **Authorized redirect URIs**:
   - `http://localhost:5173/api/auth/google/callback` (Vite dev server)
   - `http://localhost:3000/api/auth/google/callback` (Docker)
5. Copy the client ID and secret into `.env` as `GOOGLE_CLIENT_ID` and
   `GOOGLE_CLIENT_SECRET`, and set `GOOGLE_REDIRECT_URI` to whichever of the two URIs
   matches how you run the app (`:3000` for the Docker quick start).

The redirect URI in `.env` must match a registered one exactly, character for character.

### 3. Build and start

```bash
docker compose up --build
```

The backend entrypoint automatically runs `alembic upgrade head` before starting
Uvicorn. The `minio-init` service creates the configured bucket. Wait until the
backend and database health checks pass.

To start in the background:

```bash
docker compose up --build -d
docker compose ps
docker compose logs -f backend worker
```

### 4. Open the application

- Web app: <http://localhost:3000>
- FastAPI/OpenAPI docs: <http://localhost:8000/docs>
- API health: <http://localhost:8000/api/health>
- MinIO console: <http://localhost:9001>

With an unchanged `.env.example`:

- RTM login: **Sign in with Google** (requires the `GOOGLE_*` values from step 2 — see
  [Configuration](#configuration))
- MinIO login: `rtm` / `rtmsecret`

These are local development credentials only.

### 5. First-use path

1. Sign in with Google and open **Library**. **Sign in yourself first** — see the
   security note below.
2. Add a book manually, upload an EPUB from **Scraper → Upload EPUB**, or run a supported
   site scrape.
3. Open a chapter in the reader and select browser or server TTS.
4. Configure Gemini as described below if you want the assistant.

### Security notes for the Google sign-in flow

Two properties of the sign-in flow are known and accepted as designed for this
local-first stack. Neither is a bug; both matter if you expose the stack.

- **The first Google account to sign in claims the seeded admin row — and its whole
  library.** There is no email allowlist gating that claim. The intended owner must
  therefore be the first person to sign in. Until that has happened, do not expose this
  stack beyond `localhost`: whoever signs in first becomes the owner of the seeded
  account and everything already in it. After the first login the rule is spent, and
  every later Google account is provisioned as its own separate user.
- **The OAuth authorization code appears in the uvicorn access log.** This is inherent
  to the authorization-code flow — Google returns the code as a query parameter on the
  callback URL, and the access log records request lines verbatim. The application layer
  never logs the code, the ID token, or any claim. The exposure is bounded: the code is
  single-use, short-lived, and unusable without `GOOGLE_CLIENT_SECRET`. Treat access
  logs as sensitive, or disable the access log, if that residual risk matters to you.

Stop the stack with:

```bash
docker compose down
```

Add `-v` only when you intentionally want to delete PostgreSQL, Redis, and MinIO data:

```bash
docker compose down -v
```

## Get and configure a Gemini API key

The assistant is optional and disabled by default. Library, reader, TTS, scraping,
downloads, and EPUB import work without Gemini.

### Create a key

1. Sign in with a Google account at
   [Google AI Studio](https://aistudio.google.com/app/apikey).
2. Select or create a Google Cloud project.
3. Choose **Create API key** and copy the key once it is shown.
4. Review the current [Gemini API pricing and rate limits](https://ai.google.dev/pricing).
   Free-tier availability, model access, quotas, and billing requirements vary by
   account and region.
5. Restrict and rotate the key according to your deployment policy. Do not put it in
   source code, frontend environment variables, screenshots, logs, or commits.

### Configure RTM

Edit the root `.env`:

```dotenv
LLM_ENABLED=true
LLM_PROVIDER=gemini
LLM_MODEL=gemini-3.5-flash-lite
GEMINI_API_KEY=replace-with-your-key
LLM_ASSISTANT_MODE=internal_only
```

`internal_only` is the safest starting mode: the assistant can work with owned data but
external discovery/scraping tools are hidden. To let chat propose supported-site
search/import operations, use:

```dotenv
LLM_ASSISTANT_MODE=external_allowed
```

External/import operations still require a confirmation form. Restart the backend and
worker after editing `.env`:

```bash
docker compose up -d --force-recreate backend worker
```

If the configured model is unavailable for your account, choose a Gemini model that
supports function/tool calling and streaming, then update `LLM_MODEL`. Model IDs and
availability change over time; check the
[Gemini models documentation](https://ai.google.dev/gemini-api/docs/models) rather than
guessing an ID.

### Validate the integration

1. Confirm `GET /api/health` is healthy.
2. Sign in and open the assistant.
3. Ask a read-only question such as “Which books are in my library?”
4. Watch backend logs if the request fails:

```bash
docker compose logs -f backend
```

Common Gemini errors:

- **401/403:** invalid key, disabled API, project restriction, or unsupported region.
- **404 model not found:** `LLM_MODEL` is not available to that key/project.
- **429:** free-tier or project quota exhausted; wait, reduce usage, or review billing.
- **Timeout:** increase `LLM_TIMEOUT_SECONDS` carefully and inspect network access.

## Local development

### Start only infrastructure

```bash
docker compose up -d postgres redis minio minio-init
```

The root `.env.example` uses `localhost` addresses for native processes. Compose
overrides those values for containers with service DNS names such as `postgres`,
`redis`, and `minio`.

### Backend

```bash
cd backend
uv sync
uv run alembic upgrade head
uv run uvicorn app.main:app --reload --port 8000
```

The API runs at <http://localhost:8000>. Keep the worker running in a second terminal
for scraping, imports, audio jobs, and scheduled cleanup:

```bash
cd backend
uv run arq app.jobs.worker.WorkerSettings
```

For native integration tests, use a separate test database. Never point destructive
test setup at the application database:

```bash
docker compose exec postgres createdb -U rtm rtm_test
```

```dotenv
TEST_DATABASE_URL=postgresql+asyncpg://rtm:rtm@localhost:5432/rtm_test
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

The Vite app opens at <http://localhost:5173> and proxies `/api` to
<http://localhost:8000>. Leave `VITE_API_URL` empty for this workflow.

### Useful Docker commands

```bash
docker compose ps
docker compose logs -f backend
docker compose logs -f worker
docker compose restart backend worker
docker compose build backend frontend
```

## Configuration

Copy `.env.example`; it is the canonical list of supported environment variables.
Important groups:

- **Application:** `APP_ENV`, `DEBUG`
- **PostgreSQL:** `DATABASE_URL`, `TEST_DATABASE_URL`, `DB_*`
- **Redis:** `REDIS_URL`, `REDIS_PORT`
- **MinIO:** `MINIO_ENDPOINT`, `MINIO_PUBLIC_ENDPOINT`, credentials, bucket, TLS flag
- **HTTP/auth:** ports, CORS origins, `JWT_SECRET`, cookie flags, and `ADMIN_USERNAME` /
  `ADMIN_PASSWORD`. `ADMIN_PASSWORD` is **legacy and seed-only**: startup hashes it into
  a column that nothing verifies, since password login was removed. It authenticates
  nothing. `ADMIN_USERNAME` still matters — it names the seeded row that the first
  Google login claims.
- **Google SSO:** `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REDIRECT_URI` — all
  three must be set for Google sign-in to work; login endpoints return 503 while unset,
  which means nobody can sign in at all. Setup steps are in
  [Quick start step 2](#2-create-a-google-oauth-client-required-to-sign-in).
  `VITE_API_URL` must stay same-origin with the web app: the popup reports its result
  over a `BroadcastChannel` (plus an opener `postMessage` fallback), both scoped to the
  popup's own origin, so a cross-origin API base breaks sign-in even though every
  other call would still work.
- **Downloads:** `DOWNLOAD_JOB_TTL_HOURS`, `SIGNED_URL_EXPIRES_SECONDS`
- **LLM:** provider/model/key, timeout, retries, token/context limits, assistant mode,
  HITL expiry/round limits, optional Langfuse flag

Docker Compose uses the root `.env` for interpolation. A value reaches a container only
when it is listed under that service's `environment` block in `docker-compose.yml`;
backend and worker settings should normally be kept in sync. When adding a setting,
update `Settings`, `.env.example`, Compose, and this README together.

Security-sensitive production changes include:

- Use a long random `JWT_SECRET` and strong unique credentials.
- Sign in with the intended owner's Google account before anyone else can reach the app
  — the first Google login claims the seeded admin row and its library. See
  [Security notes for the Google sign-in flow](#security-notes-for-the-google-sign-in-flow).
- Treat uvicorn access logs as sensitive: the OAuth authorization code is part of the
  callback query string.
- Set `COOKIE_SECURE=true` behind HTTPS and review `COOKIE_SAMESITE`.
- Limit `CORS_ORIGINS` to trusted frontend origins.
- Use TLS-enabled PostgreSQL/Redis/MinIO or private networking.
- Put secrets in the deployment secret manager, not an image or repository.
- Set `MINIO_PUBLIC_ENDPOINT` to the browser-reachable host used in signed URLs.

## Repository structure

```text
RTM_V3/
├── backend/
│   ├── app/
│   │   ├── core/                 # config, DB, auth, logging, shared infrastructure
│   │   ├── jobs/                 # arq worker and task registration
│   │   └── modules/              # bounded contexts
│   │       ├── auth, users, library, books, chapters, reader
│   │       ├── audio, downloads, storage
│   │       ├── scraping, discovery, imports, summaries
│   │       └── llm, tools, orchestration, observability
│   ├── migrations/               # Alembic revisions
│   ├── tests/                    # backend unit/integration tests
│   ├── pyproject.toml
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── features/             # feature-owned UI, hooks, API clients, tests
│   │   └── components/           # shared UI components
│   ├── package.json
│   └── Dockerfile
├── docs/                          # product, architecture, HITL, tools, roadmap
├── .cursor/
│   ├── rules/                    # repository engineering constraints
│   └── skills/                   # repeatable implementation workflows
├── .env.example                  # canonical local configuration
└── docker-compose.yml            # full development stack
```

Most backend modules follow:

```text
modules/<name>/
├── router.py       # HTTP transport only
├── service.py      # business logic
├── repository.py  # this module's persistence
├── schemas.py      # pydantic request/response DTOs
├── models.py       # this module's SQLAlchemy models
└── tests/
```

## Engineering rules

Read `.cursor/rules/` before making structural changes. The most important invariants:

1. **Provider agnostic:** only `modules/llm` imports provider SDKs. Business modules ask
   for capabilities through `LLMProvider`.
2. **The LLM acts only through tools:** no direct DB, filesystem, service, arbitrary
   URL, or shell access.
3. **Multi-user ready:** every user-owned row and operation is ownership-scoped even
   though local setup starts with one admin.
4. **Untrusted content stays data:** scraped/book/external text cannot redefine
   instructions or approve tools.
5. **Deterministic first:** known sites use deterministic adapters; an LLM is never the
   primary parser.
6. **Respect module boundaries:** router → service → repository; cross-module calls go
   through public services.
7. **Schema changes require Alembic migrations.**
8. **State-changing/external tool actions are audited and re-authorized.**

When adding functionality:

- Put business behavior in the owning module's service.
- Keep FastAPI routers thin.
- Do not import another module's repository/models.
- Add pydantic validation at HTTP, tool, config, and structured-LLM boundaries.
- Add tests in the same slice.
- Update `.env.example` and this README when adding configuration.

## Testing and quality gates

All relevant local checks must pass before a change is considered complete.

### Backend

```bash
cd backend
uv run ruff check . --fix
uv run ruff format .
uv run ruff check .
uv run ruff format --check .
uv run mypy .
uv run pytest -m "unit or integration"
```

### Frontend

```bash
cd frontend
npm run lint
npm run format
npm run build
npm run test
```

Tests use Vitest on the frontend and pytest on the backend. Backend code is strict-mypy
typed; frontend TypeScript is strict and must not introduce `any`.

## Troubleshooting

### A port is already in use

Change the relevant root `.env` value (`FRONTEND_PORT`, `BACKEND_PORT`, `DB_PORT`,
`REDIS_PORT`, `MINIO_PORT`, or `MINIO_CONSOLE_PORT`) and recreate the stack.

### Backend waits for or cannot connect to infrastructure

```bash
docker compose ps
docker compose logs postgres redis minio backend
```

Check health status and ensure native processes use `localhost`, while Compose services
use the container values already supplied by `docker-compose.yml`.

### Database schema errors

```bash
docker compose run --rm backend alembic upgrade head
```

For native development, run `uv run alembic upgrade head` from `backend/`.

### Audio generation says ffmpeg is missing

The backend image includes ffmpeg. For a native backend install ffmpeg and verify:

```bash
ffmpeg -version
```

### Signed download URL points to the wrong host

Set `MINIO_PUBLIC_ENDPOINT` to a host and port reachable by the browser. Keep
`MINIO_ENDPOINT` as the backend/worker endpoint.

### Worker jobs do not progress

Confirm Redis and the worker are running:

```bash
docker compose ps redis worker
docker compose logs -f worker
```

### Reset local data

This permanently removes local database, queue, and object-storage volumes:

```bash
docker compose down -v
docker compose up --build
```

## Further documentation

- [`docs/assistant-capabilities.md`](docs/assistant-capabilities.md) — current assistant
  features and prompt examples
- [`docs/llm-planning/README.md`](docs/llm-planning/README.md) — LLM milestone status
  and design index
- [`docs/llm-planning/01-architecture.md`](docs/llm-planning/01-architecture.md) —
  assistant architecture and request flow
- [`docs/llm-planning/02-tools.md`](docs/llm-planning/02-tools.md) — tool catalog and
  risk classes
- [`docs/llm-planning/03-orchestration.md`](docs/llm-planning/03-orchestration.md) —
  bounded loop, budgets, context, and cancellation
- [`docs/llm-planning/04-hitl.md`](docs/llm-planning/04-hitl.md) — confirmation and
  structured-form protocol
- [`docs/phase-0-discovery.md`](docs/phase-0-discovery.md) — product discovery,
  decisions, and milestone history
- [`backend/README.md`](backend/README.md) — backend module summary and commands
