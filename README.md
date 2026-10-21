<p align="center">
  <img src="frontend/public/Logo-full.png" alt="RTM — Read To Me" width="420">
</p>

<h1 align="center">RTM v3 — Read To Me</h1>

<p align="center">
  A local-first web app for building a personal novel library: read in the browser,
  listen with text-to-speech, export MP3s, import EPUBs, scrape supported novel sites —
  and talk to a tool-gated LLM assistant that can actually <em>do</em> things, safely.
</p>

<p align="center">
  <img alt="Python 3.12" src="https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white">
  <img alt="FastAPI" src="https://img.shields.io/badge/FastAPI-modular%20monolith-009688?logo=fastapi&logoColor=white">
  <img alt="React 19" src="https://img.shields.io/badge/React-19-61DAFB?logo=react&logoColor=black">
  <img alt="TypeScript strict" src="https://img.shields.io/badge/TypeScript-strict-3178C6?logo=typescript&logoColor=white">
  <img alt="PostgreSQL + pgvector" src="https://img.shields.io/badge/PostgreSQL-pgvector-4169E1?logo=postgresql&logoColor=white">
  <img alt="Docker Compose" src="https://img.shields.io/badge/Docker-compose%20up-2496ED?logo=docker&logoColor=white">
  <img alt="Gemini" src="https://img.shields.io/badge/LLM-Gemini%20via%20provider%20abstraction-8E75B2?logo=googlegemini&logoColor=white">
</p>

---

## Contents

- [Why this project](#why-this-project)
- [Tour](#tour)
  - [Sign in and library](#sign-in-and-library)
  - [Reader, TTS, and audio downloads](#reader-tts-and-audio-downloads)
  - [Scraping and EPUB import](#scraping-and-epub-import)
  - [The assistant](#the-assistant)
  - [Admin backoffice](#admin-backoffice)
- [Feature summary](#feature-summary)
- [System architecture](#system-architecture)
- [LLM architecture and safety](#llm-architecture-and-safety)
- [Quick start with Docker](#quick-start-with-docker)
- [Enable the assistant (Gemini)](#enable-the-assistant-gemini)
- [Local development](#local-development)
- [Configuration](#configuration)
- [Repository structure](#repository-structure)
- [Engineering rules](#engineering-rules)
- [Testing and quality gates](#testing-and-quality-gates)
- [Troubleshooting](#troubleshooting)
- [Further documentation](#further-documentation)

## Why this project

RTM started as [RTM v2](https://github.com/eladjmc/RTM_V2) — a React + TypeScript
reader with a small Node backend and a site scraper, still live at
[read-to-me-beta.netlify.app](https://read-to-me-beta.netlify.app/). It proved the
idea (read and listen to long web novels in one place) but had no LLM, in-memory
jobs, and no multi-user story.

v3 is a ground-up rebuild. Two goals drove the design:

1. **A reading/listening experience that works for very long web novels** — libraries
   with thousands of chapters per book, resumable progress, server-side TTS, and
   background jobs that survive restarts.
2. **An LLM assistant that is useful but never trusted.** The model can search your
   library, summarize books, play chapters, queue MP3 exports, find and import new
   titles — but only through validated, authorized, audited tools, with a human
   confirmation step before anything external, expensive, or irreversible happens.

It runs entirely on your machine with `docker compose up`; the assistant is optional
and everything else works without an API key.

## Tour

### Sign in and library

Google SSO is the only sign-in method. The library shows cover, author, chapter count,
and where you last stopped; sort by last read, date added, name, or chapter count.

![Sign in](assets/screenshots/sign-in-page.png)

![Library](assets/screenshots/library-page.png)

Opening a book lists every chapter with the last-read marker, inline play/edit/delete,
and a filter for titles or numbers — this one has ~2,800 chapters.

![Chapter list](assets/screenshots/library-page-book-picked.png)

### Reader, TTS, and audio downloads

The reader has a player bar (play / pause / previous / next), speed and volume
controls, auto-advance, and word- or paragraph-level highlighting that follows the
voice. The settings sheet controls typography, highlight mode, speech engine, and
voice — plus **Reader text cleanup**: JavaScript regex rules (toggle on/off per rule)
that strip repeated translator/editor headers and other boilerplate before the text
is shown or read aloud.

![Reader with settings](assets/screenshots/reader-page-settings.png)

Any chapter range can be exported as a single MP3 using a local SAPI voice or Edge
neural voices. Jobs run in the background and finished files are served through
short-lived signed URLs.

<p align="center">
  <img src="assets/screenshots/manually-download-chapters.png" alt="Download audio dialog" width="640">
</p>

### Scraping and EPUB import

Seven novel sites have deterministic adapters (no LLM involved in parsing). The
Scraper page lists recent jobs with live progress, cancellation, and one-click “Open
book”; scraped chapters appear in the library as they land.

![Scraper page](assets/screenshots/scraper-page.png)

### The assistant

The assistant lives in a floating panel on every page and streams real provider output
over SSE with a live status line and a Stop button. It understands the page you are on
(“this book”), replies in the language you write in (Hebrew and English, with proper
RTL layout), and only acts through tools.

**Scraping a book by name.** The model resolves the title against the supported
sources, then pauses on a confirmation form. Approval resumes the *exact* frozen tool
call; the progress card updates live afterwards.

<table>
  <tr>
    <td><img src="assets/screenshots/scrape-book-request-llm.png" alt="Scrape request awaiting confirmation"></td>
    <td><img src="assets/screenshots/scrape-book-approved-llm.png" alt="Scrape approved and running"></td>
  </tr>
</table>

**Asking about the book, in Hebrew.** Grounded in owned content only — the model says
so when a summary is not yet available.

<table>
  <tr>
    <td><img src="assets/screenshots/asking-chat-about-the-book.png" alt="Asking about the book in Hebrew"></td>
    <td><img src="assets/screenshots/assistant-capabilities.png" alt="Assistant explaining its capabilities"></td>
  </tr>
</table>

**Creating an MP3 from chat.** “Download an MP3 of the first 5 chapters” produces a
pre-filled confirmation form (range, provider, voice, rate), then a live progress card
that turns into a download button.

<table>
  <tr>
    <td><img src="assets/screenshots/download-mp3-request.png" alt="Create audio confirmation form"></td>
    <td><img src="assets/screenshots/creating-mp3-file-from-chat.png" alt="Audio generation progress in chat"></td>
  </tr>
</table>

**Structured answers from your library.** Search across metadata, summaries, and
chapter content, rendered as a copyable/exportable table.

<table>
  <tr>
    <td><img src="assets/screenshots/request-for-table-from-library.png" alt="Searching library content"></td>
    <td><img src="assets/screenshots/result-table-from-library.png" alt="Result table of cultivation books"></td>
  </tr>
</table>

### Admin backoffice

A full admin area (admin role required) for operating the system without redeploys.

| | |
|---|---|
| **Users** — roles, membership overrides, per-user quotas, soft-delete | ![Users](assets/screenshots/admin-page-1.png) |
| **Memberships** — per-tier turn caps (iterations, external calls, tokens, cost, deadline, HITL rounds) and monthly quotas (AI tokens/spend, audio chapters, storage, scraped chapters, EPUB imports) | ![Memberships](assets/screenshots/admin-page-2.png) |
| **Runtime settings** — override allow-listed settings live; env value vs effective value side by side; clearing restores env | ![Runtime settings](assets/screenshots/admin-page-3-settings.png) |
| **AI usage & cost** — tokens, cost, executions, rejections by model / task / user for any period | ![AI usage](assets/screenshots/admin-page-4-usage.png) |
| **LLM catalog** — DB-backed providers and models with capabilities, per-1M pricing, and enablement | ![LLM catalog](assets/screenshots/admin-page-5-llm-catalog.png) |
| **Tool-call audit** — every tool execution across users with risk level, status, duration, and full input/output payloads | ![Tool-call audit](assets/screenshots/admin-page-6-tool-call-audit.png) |
| **Jobs monitor** — read-only view of all scraping and download jobs, with status and failure messages | ![Jobs monitor](assets/screenshots/admin-page-7-job-monitor.png) |

## Feature summary

### Library and reader

- Owned book library with chapters, covers, authors, and search.
- Responsive reader with dark mode, configurable typography, and saved chapter +
  word/paragraph reading position.
- Regex-based reader text cleanup rules (client-side, toggleable per rule).
- Full-text search across book metadata, stored summaries, and chapter content.

### Text-to-speech and downloads

- Browser speech, local SAPI-compatible voices, or Edge neural voices.
- Word/paragraph highlighting synced to playback, auto-advance to the next chapter.
- Single-chapter MP3 on demand; chapter-range MP3 jobs with progress, cancellation,
  and automatic download when ready.
- Files stored in MinIO, delivered through expiring signed URLs, purged after
  `DOWNLOAD_JOB_TTL_HOURS` (24 by default).

### Import, scraping, and discovery

- EPUB preview and import as bounded, chunked background work.
- Deterministic per-site adapters for **novelfull.net**, **novelbin.com**,
  **freewebnovel.com**, **novellunar.com**, **novelfire.net** (and its
  `novelphoenix.com` mirror), **ranobes.top/.net**, and **scribblehub.com**.
- Durable scrape jobs (Redis + arq) with persisted progress, retries with backoff,
  session reuse, bot-block/disconnect detection, resume from any chapter,
  cancellation, and ownership checks.
- Title/alias discovery across all sources; theme-based recommendations
  (“three books like this one, not from novelfire”) ranked and de-duplicated in a
  single bounded external call; import proposals always go through confirmation.

Scraped pages and book text are always treated as untrusted *data*, never as
instructions for the assistant.

### Controlled assistant

- Search the library, fetch book/chapter details, read or create content-hash
  invalidated summaries, answer grounded questions.
- Find reading progress and recently read chapters; navigate to, play, or resume a
  chapter.
- Create and monitor audio downloads.
- Change allow-listed, reversible UI/TTS settings.
- Discover titles and propose ranked imports; start scraping/import only after
  explicit human confirmation.
- Hebrew/English UI with RTL chat direction; replies match the user's language.
- Chat history drawer, rolling conversation summaries, cancellation, live tool status.

See [`docs/assistant-capabilities.md`](docs/assistant-capabilities.md) (Hebrew) for
working prompts and the exact current tool set.

### Admin and operations

- Google SSO; the first account to sign in claims the seeded admin row.
- Membership tiers with per-turn caps and monthly quotas, enforced server-side.
- Runtime-overridable settings, DB-backed LLM catalog, usage/cost rollups, full
  tool-call audit, and a cross-user jobs monitor.

## System architecture

RTM is a modular monolith: one FastAPI application composed of bounded-context modules,
with PostgreSQL, Redis, MinIO, an arq worker, and the React SPA running as separate
services.

```mermaid
flowchart LR
    User[Browser] --> Web[React 19 SPA<br/>Vite + Tailwind + shadcn]
    Web -->|REST + SSE| API[FastAPI modular monolith]

    API --> PG[(PostgreSQL 16<br/>pgvector)]
    API --> Redis[(Redis 7)]
    API --> MinIO[(MinIO object storage)]
    API -->|LLMProvider abstraction| Gemini[Gemini API]

    Redis --> Worker[arq worker]
    Worker --> PG
    Worker --> MinIO
    Worker --> Sources[Supported novel sites]
    Worker --> TTS[Edge / SAPI TTS]

    MinIO -->|signed expiring URL| User
```

### Service responsibilities

- **Frontend (`frontend/`)** — React Router SPA: library, reader/player, assistant
  panel, scraper/import UI, admin backoffice. React Query for server state, Zustand
  for client preferences, i18next for localization.
- **Backend (`backend/`)** — HTTP/SSE boundaries, domain services, authorization,
  persistence, LLM orchestration, tool execution, quotas, and job creation.
- **PostgreSQL + pgvector** — users, memberships, books, chapters, progress,
  conversations, summaries, jobs, runtime settings, LLM catalog, audit records, and
  usage facts/rollups. Vector support is available; RAG is deferred until retrieval
  quality measurably needs it.
- **Redis + arq** — durable queue for scraping, EPUB import, audio downloads, and
  scheduled cleanup; job rows are persisted so work resumes after restarts.
- **MinIO** — EPUB chunks and generated audio; clients only ever receive signed,
  short-lived URLs.

### Backend dependency direction

Business logic lives in services. A module may call another module's public service,
never its repository or SQLAlchemy models.

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

The model has no direct access to PostgreSQL, Redis, MinIO, the filesystem, arbitrary
websites, internal services, or a shell. It can only *propose* a call to a registered
tool; the backend validates, authorizes, rate-limits, audits, and executes it.

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
        Orch-->>UI: SSE confirmation form, turn paused
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

- **Provider abstraction:** domain code depends on capabilities (tool calling,
  structured extraction, long-context summarization), never on model names or SDK
  types. Only `modules/llm/providers/` imports a vendor SDK.
- **Tool-only actions:** every tool declares pydantic input/output schemas, a risk
  level (`read_only` / `low_risk` / `confirmation_required`), authorization, audit,
  timeout, and rate limit.
- **Ownership:** the authenticated `user_id` comes from the server session; model- or
  client-supplied identity is never trusted. Every row is ownership-scoped.
- **Assistant modes:** `internal_only` hides tools that reach external sites;
  `external_allowed` exposes them but still requires confirmation.
- **Human in the loop (HITL):** external, expensive, large, import, or destructive
  work pauses the turn and presents a structured form. Approval resumes the frozen
  call — the model cannot swap in a different action.
- **Bounded orchestration:** per-turn limits on iterations, external calls, input and
  output tokens, cost, retries, wall clock, and HITL rounds; tiers can tighten them.
- **Quotas:** monthly AI tokens/spend, audio chapters, download storage, scraped
  chapters, and EPUB imports per membership tier; refusals are recorded.
- **Context management:** recent messages stay verbatim, older context is captured in
  rolling summaries; tool rounds enforce a cumulative input-token budget.
- **Observability:** LLM executions, costs, tool calls, confirmation outcomes, and run
  IDs are persisted and visible in the admin backoffice.
- **Prompt-injection boundary:** book, scraped, tool, and route-context text is
  delimited as data and cannot select tools, alter policy, or approve actions.

## Quick start with Docker

### Prerequisites

- **Git** and **Docker Desktop** (or Docker Engine + Compose v2). On Windows, enable
  the WSL 2 backend.
- ~4 GB of free RAM for the full stack.
- Free host ports `3000`, `8000`, `5432`, `6379`, `9000`, `9001` (or change them in
  `.env`).

### 1. Clone and configure

```bash
git clone https://github.com/EladWebiks/Read-To-Me-V3-RTMLLM.git
cd Read-To-Me-V3-RTMLLM
cp .env.example .env
```

Development defaults work without an LLM key — `.env` only needs the Google OAuth
values from step 2. Before exposing the stack beyond your machine, override
`JWT_SECRET` and the database/MinIO credentials (they ship as dev-only defaults in
`backend/app/core/config.py`). Never commit `.env`; it is ignored by Git.

### 2. Create a Google OAuth client (required to sign in)

Google SSO is the only sign-in method; with `GOOGLE_CLIENT_ID` unset the login
endpoints return **503**.

1. In the [Google Cloud console](https://console.cloud.google.com/), open
   **APIs & Services → Credentials**.
2. Configure the OAuth consent screen if prompted (External, testing mode is fine) and
   add your own account as a test user.
3. **Create credentials → OAuth client ID → Web application**.
4. Add both **Authorized redirect URIs**:
   - `http://localhost:5173/api/auth/google/callback` (Vite dev server)
   - `http://localhost:3000/api/auth/google/callback` (Docker)
5. Put the client ID and secret in `.env` as `GOOGLE_CLIENT_ID` /
   `GOOGLE_CLIENT_SECRET`, and set `GOOGLE_REDIRECT_URI` to the URI that matches how
   you run the app (`:3000` for Docker).

The redirect URI must match a registered one exactly.

### 3. Build and start

```bash
docker compose up --build
```

The backend entrypoint runs `alembic upgrade head` before starting Uvicorn;
`minio-init` creates the bucket. Wait for the health checks to pass.

```bash
docker compose up --build -d      # background
docker compose ps
docker compose logs -f backend worker
```

### 4. Open the application

- Web app: <http://localhost:3000>
- OpenAPI docs: <http://localhost:8000/docs>
- API health: <http://localhost:8000/api/health>
- MinIO console: <http://localhost:9001> (`rtm` / `rtmsecret` with the default `.env`)

### 5. First-use path

1. **Sign in with Google first** — the first Google account to sign in claims the
   seeded admin row and its library (see the security note below).
2. Add a book manually, upload an EPUB from **Scraper → Upload EPUB**, or scrape a
   supported site.
3. Open a chapter in the reader and pick browser or server TTS.
4. Configure Gemini (next section) if you want the assistant.

### Security notes for the Google sign-in flow

Two properties are known and accepted by design for this local-first stack:

- **The first Google account to sign in claims the seeded admin row.** There is no
  email allowlist. Do not expose the stack beyond `localhost` until the intended owner
  has signed in; afterwards every new Google account becomes its own separate user.
- **The OAuth authorization code appears in the uvicorn access log** (it is a query
  parameter on the callback URL). The application never logs the code, ID token, or
  claims; the code is single-use, short-lived, and useless without
  `GOOGLE_CLIENT_SECRET`. Treat access logs as sensitive if that residual risk matters.

Stop with `docker compose down`; add `-v` only to delete PostgreSQL, Redis, and MinIO
data.

## Enable the assistant (Gemini)

The assistant is optional and disabled by default. Library, reader, TTS, scraping,
downloads, and EPUB import work without it.

### Create a key

1. Create an API key in [Google AI Studio](https://aistudio.google.com/app/apikey).
2. Review [Gemini pricing and rate limits](https://ai.google.dev/pricing) — free-tier
   availability and quotas vary by account and region.
3. Never put the key in source, frontend env vars, screenshots, logs, or commits.

### Configure RTM

```dotenv
LLM_ENABLED=true
GEMINI_API_KEY=replace-with-your-key
# optional
LLM_ASSISTANT_MODE=external_allowed   # default internal_only hides scraping/discovery tools
```

`LLM_PROVIDER` / `LLM_MODEL` default to `gemini` / `gemini-3.5-flash-lite`.
`LLM_ENABLED=true` without a key fails fast at startup (API and worker). Then restart:

```bash
docker compose up -d --force-recreate backend worker
```

Assistant mode and the other orchestration knobs (iteration/token/cost budgets, HITL
TTL and rounds) can also be changed live from **Admin → Settings** without a restart;
model enablement and pricing live in **Admin → LLM Catalog**.

### Validate

1. `GET /api/health` is healthy.
2. Sign in, open the assistant, ask “Which books are in my library?”.
3. If it fails, check `docker compose logs -f backend`. Common Gemini errors: 401/403
   (bad key, disabled API, region), 404 (model not available to your key), 429 (quota),
   timeouts (raise `LLM_TIMEOUT_SECONDS` carefully, or switch to a faster model).

## Local development

### Infrastructure only

```bash
docker compose up -d postgres redis minio minio-init
```

`.env.example` uses `localhost` addresses for native processes; compose overrides them
with service DNS names inside containers.

### Backend

Requires **Python 3.12**, [**uv**](https://docs.astral.sh/uv/getting-started/installation/),
and **ffmpeg** on `PATH`.

```bash
cd backend
uv sync
uv run alembic upgrade head
uv run uvicorn app.main:app --reload --port 8000
```

Run the worker in a second terminal for scraping, imports, audio, and cleanup:

```bash
cd backend
uv run arq app.jobs.worker.WorkerSettings
```

Integration tests need a **separate** test database — never point test setup at the
app database:

```bash
docker compose exec postgres createdb -U rtm rtm_test
```

```dotenv
TEST_DATABASE_URL=postgresql+asyncpg://rtm:rtm@localhost:5432/rtm_test
```

### Frontend

Requires **Node.js 20.19+ or 22.12+**.

```bash
cd frontend
npm install
npm run dev
```

Vite serves <http://localhost:5173> and proxies `/api` to <http://localhost:8000>.
Leave `VITE_API_URL` empty for this workflow.

## Configuration

Settings are grouped sub-models in `backend/app/core/config.py` — `app`, `database`,
`redis`, `storage`, `auth`, `google`, `scrape`, `audio`, `llm`, `llm_runtime`, and so
on. Those classes are the authoritative list of variables; each field's flat env name
is its `validation_alias`.

**Every setting has exactly one home:**

- A dev-correct default in the matching group class for anything tunable.
- `.env` only for real secrets (`GOOGLE_*`, `GEMINI_API_KEY` — no code default, never
  in `docker-compose.yml`) and, for native dev only, the three infra URLs
  (`DATABASE_URL`, `REDIS_URL`, `MINIO_ENDPOINT`).
- The `x-app-env` block in `docker-compose.yml` only for values compose itself
  produces or provisions.

Notes:

- `ADMIN_PASSWORD` is legacy and seed-only — password login was removed; nothing
  verifies it. `ADMIN_USERNAME` still names the seeded row that the first Google login
  claims.
- `VITE_API_URL` must stay same-origin with the web app: the sign-in popup reports its
  result over a `BroadcastChannel` scoped to its own origin.

### Runtime configuration overrides

Allow-listed settings can be overridden at runtime from **Admin → Settings** (or
`GET/PUT/DELETE /api/admin/settings[/{key}]`). Keys are `section.field`, e.g.
`llm_runtime.assistant_mode`, `llm_runtime.max_turn_cost_usd`,
`scrape.delay_seconds`, `storage.download_job_ttl_hours`.

- The whitelist is `backend/app/modules/runtime_config/registry.py`; secrets and
  infrastructure endpoints never appear in it.
- Effective value = env value unless an override row exists; deleting the override
  restores the env value. Every change is attributed and recorded in
  `app_settings_audit`.
- Values are validated against the same pydantic types and bounds as the env vars.
- Each process caches overrides for 30 seconds; the writer sees its change immediately.

### LLM model catalog and membership tiers (DB-backed)

Providers, models, capabilities, enablement, and USD-per-1M pricing live in
`model_providers` / `model_configurations`, managed from **Admin → LLM Catalog**. The
code catalog in `backend/app/modules/llm/registry.py` is seed-only: startup inserts
missing rows and never overwrites admin edits. Membership tiers follow the same
pattern (`memberships` table, **Admin → Memberships**, seed inserts only `free`).

### Production checklist

- Long random `JWT_SECRET`; strong unique DB/MinIO credentials from a secret manager.
- Sign in with the owner's Google account before anyone else can reach the app.
- Treat uvicorn access logs as sensitive.
- `COOKIE_SECURE=true` behind HTTPS; review `COOKIE_SAMESITE`; restrict `CORS_ORIGINS`.
- TLS or private networking for PostgreSQL/Redis/MinIO.
- `MINIO_PUBLIC_ENDPOINT` set to the browser-reachable host used in signed URLs.

## Repository structure

```text
RTM_V3/
├── assets/screenshots/           # README screenshots
├── backend/
│   ├── app/
│   │   ├── core/                 # config, DB, auth, logging, SSRF-guarded fetcher
│   │   ├── jobs/                 # arq worker and task registration
│   │   └── modules/              # bounded contexts
│   │       ├── auth, users, quotas, usage, admin, runtime_config
│   │       ├── library, books, chapters, reader, summaries
│   │       ├── audio, downloads, storage, job_events
│   │       ├── scraping, discovery, imports
│   │       └── llm, tools, orchestration
│   ├── migrations/               # Alembic revisions (all reversible)
│   ├── tests/                    # unit/integration tests + saved HTML fixtures
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── features/             # feature-first UI, hooks, API clients, tests
│   │   ├── shared/               # UI kit (shadcn), API client, i18n, utilities
│   │   └── layout/               # shell, navigation
│   └── Dockerfile
├── docs/                         # architecture, LLM planning, HITL, design specs
├── .cursor/rules, .cursor/skills # engineering constraints and repeatable workflows
├── .env.example
└── docker-compose.yml
```

Each backend module follows:

```text
modules/<name>/
├── router.py       # HTTP transport only
├── service.py      # business logic
├── repository.py   # this module's persistence
├── schemas.py      # pydantic request/response DTOs
└── models.py       # this module's SQLAlchemy models
```

## Engineering rules

Read `.cursor/rules/` before structural changes. The invariants:

1. **Provider agnostic:** only `modules/llm` imports provider SDKs.
2. **The LLM acts only through tools:** no direct DB, filesystem, service, URL, or
   shell access.
3. **Multi-user ready:** every user-owned row and operation is ownership-scoped.
4. **Untrusted content stays data:** scraped/book/external text cannot redefine
   instructions or approve tools.
5. **Deterministic first:** known sites use deterministic adapters; the LLM is never
   the primary parser.
6. **Respect module boundaries:** router → service → repository; cross-module calls go
   through public services.
7. **Every schema change is a reversible Alembic migration.**
8. **State-changing/external tool actions are audited and re-authorized.**
9. **Hard size limits in the frontend:** file ≤ 110 lines, function ≤ 60 lines,
   nesting ≤ 3 — enforced by ESLint; split components instead of disabling rules.

## Testing and quality gates

There is no CI; these local checks are the gate and all must pass before a change is
considered done.

```bash
# backend
cd backend
uv run ruff check . --fix && uv run ruff format .
uv run ruff check . && uv run ruff format --check .
uv run mypy .                                   # strict
uv run pytest -m "unit or integration"

# frontend
cd frontend
npm run lint                                    # eslint + prettier
npm run format
npm run build                                   # tsc -b && vite build
npm run test                                    # vitest
```

Scraping adapters have contract tests against saved HTML fixtures in
`backend/tests/fixtures/scraping/`; a fixture is added whenever a site changes.

## Troubleshooting

**A port is already in use** — change `FRONTEND_PORT`, `BACKEND_PORT`, `DB_PORT`,
`REDIS_PORT`, `MINIO_PORT`, or `MINIO_CONSOLE_PORT` in `.env` and recreate the stack.

**Backend cannot reach infrastructure** — `docker compose ps` and
`docker compose logs postgres redis minio backend`. Native processes use `localhost`;
compose services use the container values from `docker-compose.yml`.

**Database schema errors** — `docker compose run --rm backend alembic upgrade head`
(or `uv run alembic upgrade head` from `backend/` natively).

**ffmpeg missing** — the backend image includes it; for a native backend install
ffmpeg and check `ffmpeg -version`.

**Signed download URL points to the wrong host** — set `MINIO_PUBLIC_ENDPOINT` to a
browser-reachable host; keep `MINIO_ENDPOINT` for the backend/worker.

**Worker jobs do not progress** — `docker compose ps redis worker` and
`docker compose logs -f worker`.

**Scrape job failed with “blocked” or “disconnected”** — the site returned a
Cloudflare interstitial or dropped the connection. Jobs retry with backoff
automatically; re-queue from the last scraped chapter if it still fails. Some sites
(e.g. freewebnovel) may block non-browser clients entirely.

**Google sign-in suddenly fails with 401** — usually container clock drift after a
host sleep/wake (`token is not yet valid`). The verifier allows 120s of leeway;
restart Docker Desktop if drift is larger.

**Reset local data** (destructive): `docker compose down -v && docker compose up --build`.

## Further documentation

- [`docs/assistant-capabilities.md`](docs/assistant-capabilities.md) — what the
  assistant can do today, with prompt examples (Hebrew)
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
- [`docs/superpowers/specs/`](docs/superpowers/specs/) — per-feature design specs
  (SSO, runtime config, membership tiers, usage rollups, discovery, i18n, …)
- [`docs/phase-0-discovery.md`](docs/phase-0-discovery.md) — product discovery,
  decisions, and milestone history
- [`backend/README.md`](backend/README.md) — backend module summary and commands
