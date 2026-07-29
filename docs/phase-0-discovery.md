# RTM v3 — Phase 0: Discovery & Architecture

> **Status:** Historical architecture baseline; implementation underway · **Updated:** 2026-07-29
>
> This document records the original Phase 0 decisions. For current shipped assistant
> status and remaining work, see `docs/llm-planning/README.md`.

**Implementation checkpoint:** Milestone A and assistant B1–B4 are implemented. Current
Milestone C includes four-source title discovery, ranked import/scrape HITL, EPUB import,
and persisted content-hash-invalidated summaries. Theme/trope discovery and richer
grounded discussion remain.

## Legend — every claim below is labelled

| Tag | Meaning |
|-----|---------|
| **[V]** Verified | Confirmed by reading the RTM v2 / LLM project source |
| **[U]** User requirement | Explicitly stated in the RTM v3 brief |
| **[R]** Recommendation | My proposed decision + rationale |
| **[A]** Assumption | Reasonable default, **needs validation** |
| **[Q]** Open question | Must be answered before/at the relevant phase |

Reference material analysed:
- `refrence_projects/RTM_v2` — the app we are replacing (see [existing-system analysis](#5-existing-system-analysis)).
- `refrence_projects/LLM project` — an unrelated LLM app we **learn architecture from**, do not copy.

---

## 0. Locked decisions (Phase 0 outcomes)

These were decided with the stakeholder and **override any conflicting recommendation later in this doc** (kept below for rationale/history).

| # | Decision | Rationale |
|---|----------|-----------|
| D1 | **Single-user / self-hosted for v1**, but the data model is designed **multi-user-ready** (ownership FKs from day 1). | Simplifies auth/authz now; no rework later. |
| D2 | **Fresh start — no v2 data migration.** | Speed; v2 Mongo model is being replaced. |
| D3 | **Backend = Python 3.12 + FastAPI, modular monolith.** Frontend = React + TypeScript + Vite (reuse v2 UI). | LLM-heavy product; max reuse of LLM project patterns + v2 Python scraper; best LLM/RAG ecosystem (litellm, LangGraph, instructor, pydantic). |
| D4 | **LLM: build our own provider abstraction; Gemini (free key) as the first adapter.** litellm may sit *behind* the interface. | Provider-agnostic requirement; cheapest capable model (Gemini 2.5 Flash-Lite) + free dev tier. |
| D5 | **Conventions captured as both Cursor Rules (always-on) + Skills (invokable workflows)** before feature code. | Prevent drift/mistakes during development. |

**Python stack mapping** (replaces the TS-flavoured recommendations written below):

| Concern | v3 choice (locked) | (doc originally suggested) |
|---------|--------------------|-----------------------------|
| Backend framework | **FastAPI** (modular monolith) | NestJS |
| Validation/schemas | **pydantic v2** | Zod |
| ORM / migrations | **SQLAlchemy 2.0 + Alembic** (SQLModel optional) | Drizzle/Prisma |
| Jobs/queue | **Redis + arq** (Celery if scheduling grows) | BullMQ |
| Scraping | **httpx + selectolax/BeautifulSoup**, **cloudscraper** for Cloudflare, **Playwright** fallback (reuse v2 adapters) | Cheerio + Playwright |
| LLM abstraction | **`LLMProvider` protocol** (own), adapters via **litellm** / provider SDKs | own interface |
| Structured output | **instructor + pydantic** | Zod structured output |
| Orchestration | **LangGraph** (controlled graph + HITL) or hand-rolled loop | hand-rolled/LangGraph.js |
| Embeddings/vector | **pgvector** + Gemini or local (`nomic`/`bge` via Ollama) | pgvector |
| Lint/format/types | **ruff + mypy** | ESLint/tsc |
| Tests | **pytest** (markers: unit/integration/slow) | vitest/jest |

> Wherever the sections below say NestJS / Zod / Drizzle / BullMQ / TypeScript-backend, read the **Python equivalent** from the table above. Frontend remains React + TypeScript.

---

## 1. Understanding of RTM

**[U]** RTM ("Read To Me") is a web platform to **manage, read, listen to (TTS), download, scrape, search, and discuss books**, through both a normal GUI **and** a conversational LLM assistant.

**[V]** RTM v2 already delivers the "read / listen / scrape / download" core for web novels: a React SPA, an Express+MongoDB API, and a Python FastAPI scraper for 4 novel sites, with browser + server text-to-speech and MP3 export.

**[U]** RTM v3 keeps that core but rebuilds it as a **maintainable, scalable, secure, provider-agnostic** system, and adds a **controlled LLM orchestration layer** on top. The LLM is *not* a free-roaming chatbot — it acts only through explicitly defined, validated, authorized, observable **tools**. It never gets direct access to DB, filesystem, internal services, arbitrary URLs, or shell.

**[U]** v1 of RTM v3 must **run locally via Docker Compose**. Cloud deploy is out of scope for now.

**The central design tension** (and the reason this planning doc exists): v2 is a single-admin, MongoDB, Python-scraper, no-LLM app. v3 wants multi-user (implied by "personal book library"), Postgres+pgvector, a provider-agnostic LLM tool layer, and conversational scraping/discovery. We must decide **what to keep, redesign, and drop** — not port v2 verbatim.

---

## 2. Product objectives

| # | Objective | Tag |
|---|-----------|-----|
| O1 | Preserve v2's proven reading + TTS + scraping + download UX | **[U]** |
| O2 | Add a **controlled** conversational assistant over app tools | **[U]** |
| O3 | Be **provider-agnostic** (Gemini/OpenAI/Anthropic/OpenRouter/local), swap/route/compare models without touching business logic | **[U]** |
| O4 | Enforce **security-by-design**: authz, ownership, SSRF, prompt-injection resistance, signed downloads, audit | **[U]** |
| O5 | Be **observable**: tokens, cost, latency, tool success, scraping success, per model/source | **[U]** |
| O6 | Prefer a **modular monolith**; avoid unnecessary infra complexity | **[U]** |
| O7 | Ship a **Discovery database** so book search improves over time and can run **internal-only** (no external calls) | **[U]** |
| O8 | Respect **copyright / ToS / robots.txt**; treat scraped content as untrusted | **[U]** |
| O9 | Run fully **locally with Docker Compose** for v1 | **[U]** |

---

## 3. User personas

**[A]** v2 is single-admin (one env-configured user), so personas below are **proposed** for v3 and need confirmation.

| Persona | Description | Primary needs | Tag |
|---------|-------------|---------------|-----|
| **Reader** (primary) | Owns a personal library, reads & listens to novels | Fast reader, resume, TTS, offline MP3, "continue where I stopped" | **[A]** |
| **Curator/Scraper** | Adds new books by URL, manages chapters | Reliable scraping, retry/resume, progress visibility | **[V]** behaviour exists / **[A]** persona |
| **Discoverer** | Wants to *find* books not yet in library | Semantic/entity search, "book where hero plays Go" | **[U]** |
| **Admin/Operator** | Runs the instance | Model/provider config, cost dashboards, source enable/disable, audit | **[R]** |

**[Q1]** Is RTM v3 **multi-user** (accounts + per-user libraries) or still **single-user/self-hosted**? This is the single most impactful requirement — it changes auth, data model ownership, and authorization everywhere. *Default assumption: single-user/self-hosted for v1, but designed so multi-user is a later switch.* **[A]**

---

## 4. Core use cases

Grouped by phase. **[V]** = already in v2, **[U]** = new in v3.

**Reading & library (Phase 1)**
- **[V]** Log in; browse personal library (grid, search, sort).
- **[V]** Open a book → read chapter with paragraph/word highlighting.
- **[V]** TTS playback: play/pause/resume/stop/seek, prev/next chapter, speed/volume, voice pick, auto-next.
- **[V]** Resume from last read position (`lastReadPosition` = paragraph+word index).
- **[V]** Create/edit/delete books & chapters; EPUB import.
- **[V]** Download a chapter range as merged MP3; "listen while generating" jobs.

**Assistant over the library (Phase 2)**
- **[U]** "Play chapter 20 of Book X." / "Continue from where I stopped." / "What did I last read?"
- **[U]** "Show books I haven't finished." / "Create a download link for chapters 20–50." / "Summarize the last 5 chapters."

**Conversational scraping (Phase 3)**
- **[U]** "Add this book to my library: <URL>." / "Scrape chapters 20–50." / "Scrape the whole book." / "Continue from last chapter." / "Retry failed chapters." / "Show scraping progress."

**Discovery (Phase 4)**
- **[U]** "There's a book where the hero plays Go — what is it?" / "Find books similar to X." / internal-only vs internal-first vs external search.

---

## 5. Existing-system analysis

This is the **verified inventory** of RTM v2 (source: `refrence_projects/RTM_v2`). Full sub-agent report available on request.

### 5.1 Topology **[V]**
Three deployables sharing one MongoDB:
```
React 19 SPA (Vite)  ──cookie JWT──►  Express 5 API (:3001)  ──►  MongoDB (books, chapters, cleaning_rules)
       │                                     │  └► Edge TTS (msedge-tts) + SAPI proxy (texttospeechfree.io) + ffmpeg merge
       └──(local only, no auth)──►  FastAPI scraper (:8001/:8005) ──cloudscraper+BS4──► novel sites; writes MongoDB directly
```

### 5.2 Feature inventory (verified) **[V]**
- **Auth:** single admin from `ADMIN_USERNAME/PASSWORD`, JWT in httpOnly cookie `rtm_token`, 7-day. **Plaintext** password compare (bcrypt imported but unused). No users collection, no roles, no registration.
- **Books/Chapters:** Mongoose models; `(book, chapterNumber)` unique; `chapterCount` is a virtual; reading progress on the book doc.
- **Reader/TTS:** two engines — browser Web Speech API, and server TTS (Edge neural voices via `msedge-tts`, or SAPI via `texttospeechfree.io`). Word/paragraph highlight, Media Session API, wake lock, auto-next, prefetch.
- **Downloads:** chapter-range MP3 via ffmpeg merge; background "listen jobs" (in-memory, concurrency 3, temp dir, 3h TTL).
- **Scraper:** 4 adapters (`novelbin`, `novelfull`, `freewebnovel`, `novellunar`), `cloudscraper`+`BeautifulSoup`, per-chapter `next_url` walking, 1.5s delay, content cleaning rules (`cleaning_rules` collection, API-only, no UI). EPUB import. Jobs **in-memory**, direct Mongo writes.
- **Search:** client-side only over the loaded library. No server search.
- **No LLM/AI anywhere.**

### 5.3 Verified data model **[V]**
- `books`: `title`(req), `author`, `cover`(often base64 data URL), `startingChapterNumber`, `lastReadChapter`(ref), `lastReadChapterNumber`, `lastReadAt`, `lastReadPosition{paragraphIndex, wordIndex}`, timestamps, virtual `chapterCount`.
- `chapters`: `book`(ref, indexed), `chapterNumber`, `title`, `content`(req full text), timestamps. Unique `(book, chapterNumber)`.
- `cleaning_rules`: `bookId?`, `pattern`, `action`, `replacement`, `description`, `enabled`.
- Scraper `upsert_book` matches **by title only** (distinct books with same title collide).

### 5.4 Scraper adapter interface (verified — this is gold for v3) **[V]**
`app/sources/base.py` + each source implement:
`matches(url)`, `derive_book_url(url)`, `fetch_book_metadata(url) -> BookMetadata{cover,title,author}`, `parse_chapter_page(url) -> ChapterData{title,content,next_url,book_title,book_author,chapter_number}`, `get_next_chapter_url(...)`, `is_placeholder_chapter(...)`. This maps almost 1:1 onto the v3 adapter interface the brief requests.

### 5.5 Technical debt to fix in v3 **[V]**
1. In-memory jobs (scrape/import/listen) → lost on restart, can't scale, no retry/resume durability.
2. Plaintext password; auth/doc drift (docs say localStorage JWT, code uses cookies).
3. Scraper: open CORS `*`, **no auth**, writes prod DB directly, `upsert_book` by title collision, port mismatch (8001 vs 8005).
4. Cover stored as base64 in DB (bloats documents) → should be object storage.
5. Dead code (`windows-tts.service.ts`, `audioDownload.ts`, unused HLS playlist, `renumberChaptersAfter` never called → delete leaves gaps).
6. No server-side search, no pagination.
7. No structured logging/metrics/tracing.

### 5.6 What LLM project teaches us (reference architecture) **[V]**
LLM project is a **modular monolith** (FastAPI + LangGraph) with strong patterns we should adapt — **but it is single-provider (Gemini/Vertex only) with no provider abstraction and no classic tool-calling** (it makes the LLM emit SQL that is then validated). Reusable ideas:
- **`LLMBase.invoke(caller=...)`** wrapper: system-prompt composition, per-caller generation overrides, token→DB logging. Adapt behind a real provider interface.
- **Prompt provider** with remote + local-file fallback.
- **Checkpointer + per-conversation Redis lock** to stop concurrent runs corrupting state.
- **SSE-first streaming** protocol (trace steps, text, HITL, results); run the orchestration in a worker so the event loop stays free.
- **HITL via interrupt + resume endpoint**, with a **max-rounds** cap → maps directly to our "confirmation required" tools.
- **Observability split:** LLM traces (Langfuse) vs product timing/cost table in Postgres (`timing_events`) vs infra (Prometheus/Grafana).
- **Executable-artifact safety:** treat any generated action like untrusted output — parse, allowlist, authorize. Mirror this for our tools.
- **Anti-patterns to avoid:** no provider abstraction, infra-only Prometheus (no app `/metrics`), background work on raw thread pools with no durable queue.

---

## 6. Questions the reference app / stakeholder must answer

| # | Question | Blocks | Tag |
|---|----------|--------|-----|
| Q1 | Multi-user or single self-hosted for v1? | Auth, data model, authz | **[Q]** |
| Q2 | Which languages must TTS support? v2 defaults en-US Edge voices. Any Hebrew/other? | TTS provider choice | **[Q]** |
| Q3 | Keep both TTS engines (browser + server) or standardize? Is `texttospeechfree.io` (SAPI proxy) acceptable long-term, or move to a proper TTS provider? | Audio module | **[Q]** |
| Q4 | Are the 4 v2 sites the full supported set, or add more? Is Cloudflare bypass (v2 used `cloudscraper`) still required? | Scraping stack | **[Q]** |
| Q5 | Copyright posture: is this personal/self-hosted use, or a service? Which sources are legally enabled? | Legal, source config | **[Q]** |
| Q6 | Which LLM providers do you actually have keys for on day 1 (for Phase 2)? | Provider adapters | **[Q]** |
| Q7 | Is EPUB import still required in v3? | Import module | **Yes** — Scraper → Upload EPUB (v2 parity) |
| Q8 | Data migration: import existing v2 Mongo library into v3 Postgres, or start fresh? | Migration | **[Q]** |
| Q9 | Budget/latency ceilings for LLM calls (affects model routing & summarization strategy)? | Model routing | **[Q]** |
| Q10 | Do we need an admin UI in v1, or env/config-file driven model & source config? | Admin module | **[Q]** |

---

## 7. Proposed feature inventory (v3)

| Capability | Disposition | Tag |
|------------|-------------|-----|
| Auth (login/logout/session) | **Redesign** — hashed passwords, proper sessions, multi-user-ready | **[R]** |
| Personal library, book/chapter CRUD | **Retain** | **[V]/[R]** |
| Reader with highlight | **Retain** | **[V]** |
| Reading progress + resume | **Retain**, move to relational model | **[V]/[R]** |
| Browser + server TTS | **Retain, abstract behind a `TtsProvider`** | **[R]** |
| Chapter-range MP3 download + listen jobs | **Retain, make durable** (BullMQ + object storage + signed URLs) | **[R]** |
| Scraping (4 sites) + EPUB import | **Retain adapter concept, re-implement durable + authz'd** | **[R]** |
| Content cleaning rules | **Retain**, add UI | **[R]** |
| Cover images | **Redesign** — object storage, not base64 in DB | **[R]** |
| Server-side search (books/chapters) | **Add** (Postgres FTS) | **[R]** |
| Conversational assistant + tools | **Add** (Phase 2) | **[U]** |
| Conversational scraping | **Add** (Phase 3) | **[U]** |
| Discovery DB + internal/external search | **Add** (Phase 4) | **[U]** |
| Provider-agnostic LLM + routing | **Add** (Phase 2, foundation earlier) | **[U]** |
| Observability (cost/tokens/latency/success) | **Add** | **[U]** |
| Remove: dead code, base64 covers, in-memory jobs, unauth scraper | **Remove** | **[V]** |

---

## 8. Functional requirements (selected, by phase)

**Phase 1 — Core**
- FR1 Users authenticate; all book data is scoped to the owner. **[R]**
- FR2 CRUD books & chapters; unique chapter number per book; deletes are soft where feasible. **[R]**
- FR3 Reader renders chapter, tracks progress (chapter + paragraph + word), resumes on reopen. **[V]**
- FR4 TTS: play/pause/resume/seek/prev/next/speed/volume/voice/auto-next, via a provider abstraction. **[V]/[R]**
- FR5 Generate a merged MP3 for a chapter range as a **durable background job**; deliver via a **signed, expiring URL**. **[R]**
- FR6 Server-side book + chapter search (FTS). **[R]**

**Phase 2 — Assistant**
- FR7 Chat endpoint streams (SSE) assistant turns; the LLM may only act via registered tools. **[U]**
- FR8 Each tool has input/output pydantic schemas, authz, validation, error handling, audit log, rate limit, idempotency where relevant, timeout. **[U]**
- FR9 Tools are classified read-only / low-risk / confirmation-required; confirmation-required tools pause for user approval (HITL). **[U]**

**Phase 3 — Conversational scraping**
- FR10 From a URL, validate → identify source → preview (metadata, first chapter, est. count) → confirm → durable job → progress/retry/resume/cancel. **[U]**
- FR11 Scraping supports range/full/resume/retry/dedup/missing-detection/idempotency/concurrency+per-site throttle. **[U]**

**Phase 4 — Discovery**
- FR12 Discovery search with scopes `internal_only` / `internal_first` / `external_allowed`; internal-only makes **zero external requests**. **[U]**
- FR13 Externally found books are normalized and persisted (books, sources, aliases, entities, facts w/ provenance) for future internal search. **[U]**

---

## 9. Non-functional requirements

| Area | Requirement | Tag |
|------|-------------|-----|
| Portability | Full stack runs via `docker compose up` locally; no cloud dependency required | **[U]** |
| Security | See [§17 Security model](#17-security-model) — provider-agnostic, SSRF-safe, prompt-injection resistant | **[U]** |
| Provider-agnosticism | No business logic imports a concrete LLM SDK; depends only on interfaces | **[U]** |
| Observability | LLM/scraping/jobs measurable per model & source | **[U]** |
| Maintainability | Strict typing (mypy) + pydantic validation at all boundaries, clear module boundaries, tests | **[U]** |
| Performance | **[A]** reader interactions < 200 ms server time; TTS synth streamed; long work always async | **[A]** |
| Scalability | **[R]** stateless API + Redis/queue so it *can* scale horizontally later, even if v1 is single-node | **[R]** |
| Reliability | Durable jobs survive restart; idempotent scraping; graceful LLM fallback | **[U]** |
| Cost control | Token/cost budgets per conversation & per task; cheap models for cheap tasks | **[U]** |

---

## 10. Recommended architecture

**[R] Modular monolith, Python (FastAPI) backend + React/TS frontend, Postgres-centric, Docker Compose.** (See [§0 locked decisions](#0-locked-decisions-phase-0-outcomes).)

### 10.1 Stack decision (locked)

| Concern | Choice | Rationale | Tag |
|---------|--------|-----------|-----|
| Backend | **Python 3.12 + FastAPI** (modular monolith, package-per-module) | LLM-heavy product; reuse LLM project patterns + v2 scraper; best LLM/RAG ecosystem | **[U]/[R]** |
| Frontend | **React + TypeScript + Vite** | Matches v2 (React 19, Vite, Tailwind 4, shadcn, react-query, zustand) — reuse UI knowledge & components | **[U]/[V]** |
| DB | **PostgreSQL + pgvector** | Relational integrity for ownership/jobs/facts; pgvector for discovery embeddings; FTS for search — one engine instead of Mongo | **[U]** |
| ORM/migrations | **SQLAlchemy 2.0 + Alembic** (SQLModel optional) | Typed models, first-class migrations | **[R]** |
| Validation/schemas | **pydantic v2** (HTTP DTOs, tool I/O, config, LLM structured output) | Single validation story; tool schemas double as LLM function schemas | **[U]** |
| Queue/jobs | **Redis + arq** (Celery if scheduling grows) | Durable async jobs w/ retry/concurrency — fixes v2's in-memory jobs | **[U]** |
| Scraping | **httpx + selectolax/BeautifulSoup**, **cloudscraper** (Cloudflare), **Playwright** fallback | Reuse v2's proven adapters; deterministic first, browser only when needed | **[U]/[R]** |
| LLM abstraction | **own `LLMProvider` protocol**, adapters via **litellm** / provider SDKs; **instructor** for structured output | Provider-agnostic; swap/route models without touching business logic | **[U]** |
| Object storage | **MinIO** (S3-compatible) in compose | Covers, generated MP3s, HTML/extraction traces; signed URLs; keeps blobs out of DB | **[U]** |
| Streaming | **SSE** (FastAPI `StreamingResponse`/`sse-starlette`) | Sufficient for chat + progress; LLM project confirms viability | **[U]/[V]** |
| LLM traces | **Langfuse** (optional, compose profile) | Proven in LLM project; gate behind a profile so `internal_only`/offline still works | **[R]** |
| Metrics | **Prometheus + Grafana** (optional profile) + app `/metrics` (`prometheus-fastapi-instrumentator`) | Fix LLM project's gap (it had infra-only metrics) | **[R]** |
| Lint/format/types/tests | **ruff + mypy + pytest** | Strict typing + fast tooling | **[R]** |

### 10.2 Layering (dependency direction ↓)
```
UI (React SPA)
  └─ HTTP/SSE ─► API layer (FastAPI routers, pydantic DTOs, authz dependencies)
                   └─► Application/Domain services (business logic — no LLM/provider imports)
                         ├─► Tool layer (registry, schemas, authz, audit)  ◄── LLM Orchestrator
                         │                                                     └─► LLM Provider abstraction ─► adapters (Gemini/OpenAI/Anthropic/OpenRouter/Local)
                         ├─► Scraping module (adapters + fetch service + SSRF guard)
                         ├─► Jobs (arq producers/workers)
                         └─► Persistence (Drizzle repos) ─► Postgres/pgvector
Infra: Redis, MinIO, (Langfuse, Prometheus/Grafana optional)
```
**Golden rule [U]:** domain/business services never import a provider SDK; the **orchestrator** calls **tools**; **tools** call domain services; the LLM only ever sees tool schemas.

---

## 11. Module boundaries

Proposed FastAPI modules (each = Python package with `router.py` / `service.py` / `repository.py` / `schemas.py` / `models.py` / `tests/`). **[R]**

| Module | Responsibility | Phase |
|--------|----------------|-------|
| `auth` | Login, sessions/tokens, password hashing | 1 |
| `users` | User profile, settings, ownership root | 1 |
| `library` | User↔book membership, favorites, history | 1 |
| `books` | Book metadata, covers (via storage) | 1 |
| `chapters` | Chapter content, numbering, ordering | 1 |
| `reader` | Reading progress, resume, sessions | 1 |
| `audio` | TTS provider abstraction, synth, playback state | 1 |
| `downloads` | MP3 generation jobs, signed URLs | 1 |
| `search` | Postgres FTS over books/chapters | 1 |
| `storage` | S3/MinIO wrapper, signed URLs | 1 |
| `jobs` | arq setup, queues, workers, progress events | 1 |
| `scraping` | Source registry, adapters, fetch service, cleaning | 3 (adapter skeleton usable in 1 for import) |
| `discovery` | DiscoveredBook/sources/aliases/entities/facts, hybrid search | 4 |
| `chat` | Conversations, messages, SSE streaming | 2 |
| `llm` | Provider interface + adapters, model registry, routing | 2 (foundation early) |
| `orchestration` | Tool loop, budgets, HITL, tracing | 2 |
| `tools` | Tool registry + individual tool defs (authz/audit) | 2 |
| `observability` | Metrics, cost/token recording, audit log | cross-cutting |
| `admin` | Provider/model/source config, dashboards | 2+ |
| `notifications` | Job completion / progress notices | optional |

---

## 12. Initial domain model

**[R]** Relational (Postgres). Ownership via `user_id` FK on user-scoped tables; soft-delete (`deleted_at`) on user content; `created_at/updated_at` everywhere. Vector columns on `chapters` and `discovered_books` for semantic search.

### 12.1 Core (Phase 1)
- **user**(id, email/username, password_hash, role, created_at) — **[R]** replaces v2 env-admin.
- **book**(id, canonical_title, normalized_title, author, description, language, cover_object_key, status, source_ref?, created_at, updated_at, deleted_at).
- **user_book**(user_id, book_id, is_favorite, added_at, PK(user_id,book_id)) — **[R]** membership so a book can be shared/deduped across users.
- **chapter**(id, book_id, chapter_number, title, content, content_hash, word_count, embedding?, created_at, updated_at, deleted_at; UNIQUE(book_id, chapter_number)) — **[V]** carried from v2.
- **reading_progress**(id, user_id, book_id, chapter_id, chapter_number, paragraph_index, word_index, updated_at; UNIQUE(user_id, book_id)) — **[V]** shape from v2 `lastReadPosition`.
- **reading_session**(id, user_id, book_id, chapter_id, started_at, ended_at, ...) — **[R]** analytics/history.
- **playback_state**(id, user_id, book_id, chapter_id, position_ms, engine, voice, rate, updated_at) — **[R]** (v2 kept this in localStorage).
- **cleaning_rule**(id, book_id?, pattern, action, replacement, enabled) — **[V]**.

### 12.2 Jobs & downloads
- **download_job**(id, user_id, book_id, chapter_from, chapter_to, provider, voice, status, object_key, expires_at, error, created_at) — durable (replaces in-memory).
- **job**(generic) or per-queue rows; progress persisted so restarts recover — **[R]** (LLM project `layer_recovery` pattern).

### 12.3 Scraping (Phase 3)
- **scraping_source**(id, name, base_domains[], enabled, robots_policy, rate_limit, terms_note) — config + **[U]** copyright control.
- **scraping_job**(id, user_id, source_id, book_id?, start_url, mode[range|full|resume|retry|missing], chapter_from?, chapter_to?, status, stats, created_at).
- **scraping_job_item**(id, job_id, chapter_number, url, status[pending|ok|failed|skipped], attempts, error, raw_html_key?, extracted_hash) — enables retry/dedup/missing detection + trace retention.

### 12.4 Discovery (Phase 4)
- **discovered_book**(id, canonical_title, normalized_title, alt_titles[], author, description, language, genres[], themes[], cover_key, publication, status, embedding, timestamps).
- **book_source**(id, discovered_book_id, source_website, source_url, source_identifier, raw_title, raw_description, book_page_url, first_chapter_url, last_checked_at, extraction_version, metadata jsonb).
- **book_alias**(id, discovered_book_id, alias, type[alt|translated|abbrev|translit], normalized_alias).
- **book_entity**(id, discovered_book_id, type[character|location|game|profession|ability|org|theme|trope|object], name, normalized_name).
- **book_fact**(id, discovered_book_id, entity_id?, claim, source, confidence, extraction_method, supporting_text, created_at) — **[U]** provenance mandatory; **an unsupported LLM inference is never stored as a verified fact.**

### 12.5 LLM / conversation / cost
- **conversation**(id, user_id, title, created_at) ; **conversation_message**(id, conversation_id, role, content, tokens_in, tokens_out, created_at).
- **tool_call**(id, message_id, tool_name, input jsonb, output jsonb, status, duration_ms, risk_level, confirmed_by_user, error, created_at) — audit.
- **llm_execution**(id, conversation_id?, task, provider, model, tokens_in, tokens_out, cost, latency_ms, status, fallback_used, trace_id, created_at).
- **model_provider**(id, name, enabled, config jsonb) ; **model_configuration**(id, provider_id, model_name, capabilities[], context_window, supports_tools, supports_structured, supports_streaming, enabled).
- **cost_record**(id, llm_execution_id, model, tokens_in, tokens_out, unit_cost, total_cost, created_at) — cost dashboards.
- **audit_log**(id, user_id, action, resource, metadata jsonb, created_at) — cross-cutting security audit.

**Constraints/indexes [R]:** FKs with `ON DELETE` care; `UNIQUE(book_id, chapter_number)`, `UNIQUE(user_id, book_id)` for progress; GIN indexes for FTS + `alt_titles`/`genres`; ivfflat/hnsw on `embedding`; partial indexes on `status` for job queues.

---

## 13. LLM provider abstraction

**[U]** The whole app depends on an interface, never a vendor. Proposed shape (TS):

```ts
export interface LLMProvider {
  readonly name: string;
  readonly capabilities: ModelCapability[];
  generateText(req: GenerateTextRequest): Promise<GenerateTextResponse>;
  streamText(req: GenerateTextRequest): AsyncIterable<StreamChunk>;
  generateStructuredOutput<T>(req: StructuredOutputRequest<T>): Promise<T>; // Zod-schema validated
  callTools(req: ToolCallingRequest): Promise<ToolCallingResponse>;
  createEmbeddings?(req: EmbeddingRequest): Promise<EmbeddingResponse>;
}
```
Adapters **[U]**: `GeminiProvider`, `OpenAIProvider`, `AnthropicProvider`, `OpenRouterProvider`, `LocalModelProvider` (Ollama/vLLM).

**Model registry & routing [U]:** business code requests a **capability**, not a model name.
Capabilities: `FAST_CHAT`, `TOOL_CALLING`, `STRUCTURED_EXTRACTION`, `LONG_CONTEXT_SUMMARIZATION`, `RERANKING`, `EMBEDDING`, `LOCAL_PRIVATE_INFERENCE`.
A **router** maps `(task, capability, constraints)` → ordered candidate models, with:
- fallback chain, retry policy, timeout, circuit breaker (per provider), **[U]**
- feature detection (does model support tools/structured/streaming?) so we don't send unsupported requests, **[U]**
- cost/token/latency recording on every call (→ `llm_execution`, `cost_record`). **[U]**

**[R]** Do **not** assume providers share request format, tool schema, token accounting, or system-prompt semantics — each adapter normalizes to our internal types (learned from LLM project being locked to one provider).

**[R]** Reuse LLM project's `LLMBase.invoke(caller=...)` idea: a thin call wrapper that composes the system prompt, applies per-task generation overrides (temperature/seed), records tokens, and links the trace — but sitting **behind** the provider interface.

---

## 14. Tool architecture

**[U]** LLM acts only through tools. Every tool declares:
`name, description, inputSchema (Zod), outputSchema (Zod), riskLevel, requiresConfirmation, readOnly, touchesExternal, allowedInInternalOnly, rateLimit, idempotencyKey?, timeoutMs, authorize(ctx), execute(input, ctx)`.

**Execution contract [U]:** LLM proposes a tool + args → orchestrator validates args (Zod) → checks authz + ownership (`ctx.userId`) → checks risk/confirmation & mode (`internal_only`) → rate-limit/idempotency → execute with timeout → validate output → **audit log (`tool_call`)** → return structured result to the model. The **backend is authoritative**; the model never executes anything itself.

**Risk levels [U]:**
- **Read-only:** `search_user_books`, `get_book_details`, `get_reading_progress`, `get_recently_read_chapters`, `get_chapter_content`, `list_available_chapters`, `get_download_status`, `search_library_content`, `search_internal_discovery`.
- **Low-risk actions:** `play_chapter`, `pause/resume playback`, `open_book_page`, `create_chapter_download` (small).
- **Confirmation-required (HITL):** scrape full book / large range, overwrite/delete chapters or books, large archive, **access external websites**, import externally discovered book, retry a large failed job.

Phase-2 tool set (from brief): `search_user_books`, `get_book_details`, `get_reading_progress`, `get_recently_read_chapters`, `get_chapter_content`, `play_chapter`, `resume_book`, `list_available_chapters`, `create_chapter_download`, `get_download_status`, `search_library_content`. **[U]**

**Orchestration loop [U]** (adapt LLM project's controlled pipeline + HITL): conversation state, tool registry, tool-execution loop with **max iterations / max external requests / max token budget / max wall-clock**, cancellation, retries, fallback, confirmation gates, user-visible progress (SSE), trace IDs, audit, cost accounting. **No uncontrolled agent loops.**

**[Q11]** Implement the loop with a framework (LangGraph.js / Vercel AI SDK) or hand-rolled? **[R]** start hand-rolled + Zod for full control and provider-agnosticism; revisit if complexity grows (ADR).

---

## 15. Scraping architecture

**[U/R]** Deterministic **per-site adapters** (preferred) with an LLM **fallback** only for irregular pages.

Adapter interface (derived from the **verified** v2 interface, extended per brief) **[U/V]**:
`supports_url`, `parse_book_page`, `extract_book_metadata`, `find_first_chapter`, `parse_chapter`, `find_next_chapter`, `find_previous_chapter`, `estimate_chapter_count`, `validate_chapter_sequence`.

**Pipeline [U]:** validate URL → identify source → adapter parse metadata → find first chapter → determine navigation → **preview** to user → **confirm** (large/destructive) → durable BullMQ job → per-chapter items (retry/resume/dedup/missing/idempotency) → progress/failure/completion events (SSE).

**Fetch service [U/R]:** central outbound fetcher enforcing SSRF guard (allowlist of source domains, block private IPs, DNS-rebinding protection), per-site rate limit/throttle, timeouts, response-size limits; Cheerio for static HTML, Playwright for JS/Cloudflare; optional raw-HTML/extraction-trace retention in MinIO for regression fixtures.

**[U]** LLM is **not** the primary HTML parser for known sites. **Scraped content is untrusted** and can never redefine instructions, select tools, or expose secrets (sanitize + isolate; see security).

**Concurrency/durability [U]:** BullMQ concurrency + per-source rate limiter; job cancellation; safe restart (recover in-progress items); dedup by `content_hash`.

**[Risk R1]** Porting v2's Python `cloudscraper` Cloudflare handling to Node is the biggest scraping risk (see [§22](#22-risks-and-mitigations)).

---

## 16. Search & discovery architecture

**[U]** Hybrid retrieval; the LLM assists but is never the only mechanism.

**Layers:** exact title → normalized title → alias → Postgres FTS → fuzzy (`pg_trgm`) → semantic (pgvector) → metadata/entity/source/language filters → optional LLM rerank.

**Scopes [U]:**
- `internal_only` — **zero external requests**; search only discovered books, scraped metadata, user libraries, stored summaries/entities/aliases/sources, embeddings/indexes. (Compose must run this with LLM/network features off — hence Langfuse/metrics behind profiles.)
- `internal_first` — internal first; go external only when confidence is low.
- `external_allowed` — internal + selected external source adapters (controlled search tools, **not** autonomous browsing).

**LLM roles [U]:** intent detection, query decomposition/expansion, translation, entity extraction, candidate reranking, clarification questions, response generation — always over retrieved candidates.

**Persistence of findings [U]:** external results are normalized into `discovered_book`/`book_source`/`book_alias`/`book_entity`/`book_fact` with provenance + confidence so future searches are internal. **[Q12]** External discovery sources (which sites/APIs) to be evaluated per brief criteria (search quality, ToS, robots.txt, API availability, multilingual, linkability to a scraping source).

---

## 17. Security model

**[U]** Design covers all of:
- **AuthN/session:** hashed passwords (argon2/bcrypt — fix v2 plaintext), secure httpOnly cookies or tokens, CSRF protection, session expiry.
- **AuthZ + ownership:** every resource access checks `userId` ownership; tools re-check authz independently of the LLM.
- **Input validation:** Zod at every boundary (HTTP, tools, config, LLM structured output).
- **SSRF:** central fetcher with domain allowlist, block private/link-local IPs, DNS-rebinding protection, timeouts, response-size caps — applied to scraping **and** any external discovery.
- **Content safety:** sanitize scraped HTML (strip scripts), XSS protection in reader, treat all scraped/book text as **untrusted data**, isolated from system prompt.
- **Prompt-injection resistance:** system prompt is authoritative; external/book content is clearly delimited as data; tools (not text) authorize actions; the model cannot expose secrets or escalate; confirmation gates for destructive/external tools.
- **DB:** parameterized queries only (Drizzle/Prisma) — no string SQL.
- **Downloads:** authorization + **signed, expiring URLs** (MinIO), no direct object access.
- **Rate limiting:** per-user, per-tool, per-source.
- **Secrets:** `.env` + compose secrets locally; never logged; provider keys isolated in the `llm` module.
- **Audit:** `audit_log` + `tool_call` for every state-changing/external action.
- **LLM data minimization:** send the model only what a task needs; consider provider data-retention; `LOCAL_PRIVATE_INFERENCE` capability for sensitive ops.
- **Copyright/ToS [U]:** per-source enable/disable, robots.txt + rate-limit honoring, retention/deletion policy, attribution, restricted download generation; don't assume all reachable text may be stored/distributed.

---

## 18. Observability plan

**[U]** Make LLM + scraping measurable.

- **LLM/cost:** record every call to `llm_execution` + `cost_record` (requests/tokens/cost/latency per model, fallback rate, invalid-structured-output rate, agent iteration count). Optional **Langfuse** for rich traces (compose profile; off in `internal_only`).
- **Tools:** success/failure rate, per-tool latency, confirmation rate (from `tool_call`).
- **Scraping:** success/failure by source, chapter-extraction failures, retry counts, per-source throughput.
- **Downloads/jobs:** generation time, queue depth, failure rate.
- **Search:** internal-vs-external rate, cache hit rate, result relevance, user selection from results.
- **Infra:** app `/metrics` (fix LLM project gap) scraped by **Prometheus**, dashboards in **Grafana** (compose profile).
- **Logging:** structured logs w/ trace/correlation IDs; **[U] never log full private book content or sensitive prompts** unless explicitly required and protected.

---

## 19. Testing strategy

**[U]** Layers:
- **Unit** — domain services, model router, tool authz, adapters (parsing).
- **Integration** — API + DB + Redis + MinIO via test compose.
- **Contract tests** — for each **LLM provider adapter** (normalized behaviour) and each **scraping adapter** (against saved HTML fixtures → regression).
- **Security tests** — tool authorization matrix, **prompt-injection** suite, **SSRF** suite.
- **Queue/retry tests** — job durability, resume, idempotency, dedup.
- **DB migration tests** — up/down, seed.
- **E2E** — Playwright for reader/TTS/scraping happy paths.
- **LLM evaluations [U]** — repeatable datasets (not vibes) for **tool-selection**, structured-output validity, summary quality, search relevance; **cost regression** tests. (Adapt LLM project's `research/eval` approach.)

**[R]** No CI for now — lint + format + typecheck + tests are run **locally before every commit** as the gate (see rule `85-linting-and-types`). E2E + eval run on demand.

---

## 20. Development milestones (locked delivery order)

Stakeholder-aligned milestones. Architecture still supports discovery later; delivery order prioritizes **v2 parity first**, then LLM.

| Milestone | Scope | Key deliverables |
|-----------|-------|------------------|
| **0** | Discovery & architecture | This plan + rules/skills + ADRs list |
| **A — v2 parity, better** | Reading + library + scraping (+ TTS/downloads), no real LLM | Auth/users, library, books/chapters, reader + progress, TTS, downloads (arq+MinIO), scraping (4 adapters, durable jobs), FTS search, Docker Compose. **Chat UI placeholder on the reader page** (layout/UX only — no backend, no tools). |
| **B — basic LLM** | Wire the chat shell to a real assistant | `LLMProvider` + Gemini adapter, chat API + SSE, orchestrator + budgets, read-only / low-risk tools (`search_user_books`, `play_chapter`, `resume_book`, …) |
| **C — full assistant** | End-to-end conversational product | Confirmation-gated scrape/download tools, summaries, richer library Q&A; discovery (internal/external) if still desired |

**[R]** Milestone A ships with **zero LLM dependency**. The reader chat panel is UI-only until B.

---

## 21. Dependencies between milestones

```
P0 ─► A (parity + chat placeholder) ─► B (basic LLM tools) ─► C (scrape/play/discuss via chat + discovery)
```
- A establishes domain services, jobs, scraping, storage, observability skeleton.
- B depends on A (tools call A domain services) + provider abstraction.
- C extends B with confirmation-gated / expensive tools and optional discovery.
- Cross-cutting (security, ownership, lint gates) established from day 1 of A.

---

## 22. Risks and mitigations

| # | Risk | Impact | Mitigation | Tag |
|---|------|--------|------------|-----|
| R1 | **Cloudflare bypass** — v2 relied on Python `cloudscraper`; Node has no direct equivalent | Scraping breaks for protected sites | Use Playwright (real browser) for protected sites; optional **FlareSolverr** sidecar; keep adapter interface fetcher-agnostic; **[Q4]** confirm which sites need it | **[V]→R** |
| R2 | Porting 4 Python adapters + cleaning rules to TS | Effort + parsing regressions | Save v2 HTML fixtures → **contract tests** guarantee parity; port one adapter first as a template | **[R]** |
| R3 | Provider API divergence (tools/structured/tokens) | Leaky abstraction | Normalize in adapters; feature detection; contract tests per provider | **[U]** |
| R4 | Prompt injection via scraped/book content | Data exfiltration, unwanted actions | Untrusted-data delimiting, tool-only authorization, confirmation gates, no secrets in context, injection test suite | **[U]** |
| R5 | SSRF via user-provided URLs | Internal network access | Central fetcher + allowlist + private-IP block + DNS-rebind protection | **[U]** |
| R6 | LLM cost/loops runaway | Bill + latency | Budgets (tokens/iterations/time), circuit breakers, cheap-model routing, cost regression tests | **[U]** |
| R7 | Copyright/ToS exposure | Legal | Per-source enable/disable, robots/rate honoring, retention/deletion, **[Q5]** posture | **[U]** |
| R8 | Scope creep (4 phases at once) | Never ships | Strict phase gates; P1 must be usable without any LLM | **[R]** |
| R9 | Multi-user ambiguity (**[Q1]**) reworks data model late | Rework | Decide Q1 now; design ownership in from day 1 even if v1 is single-user | **[Q]** |
| R10 | Mongo→Postgres migration fidelity | Data loss | Optional, scripted, idempotent importer w/ validation; **[Q8]** | **[R]** |

---

## 23. Architecture Decision Records to create

**[R]** Author these ADRs (in `docs/adr/`) before/at their phase. (ADR-001/002/003/010 outcomes already fixed by [§0](#0-locked-decisions-phase-0-outcomes) — write them up to record rationale.)
1. ADR-001 Modular monolith + **FastAPI (Python)** — *decided (D3)*.
2. ADR-002 PostgreSQL + pgvector as single datastore (vs keep Mongo) — *decided*.
3. ADR-003 **SQLAlchemy 2.0 + Alembic** (vs SQLModel) — *decided*.
4. ADR-004 LLM provider abstraction & model-router design (own `LLMProvider` + litellm).
5. ADR-005 Orchestration: **LangGraph** vs hand-rolled tool loop.
6. ADR-006 Scraping engine: httpx + selectolax + cloudscraper (± Playwright/FlareSolverr) & SSRF fetcher.
7. ADR-007 TTS provider abstraction (keep browser+Edge+SAPI vs standardize).
8. ADR-008 Jobs on **Redis + arq**; durability/recovery model.
9. ADR-009 Object storage (MinIO) + signed URLs; covers/audio out of DB.
10. ADR-010 Auth & **single-user-now / multi-user-ready** model — *decided (D1)*.
11. ADR-011 Observability stack (Langfuse + Prometheus/Grafana behind compose profiles).
12. ADR-012 Discovery search strategy & fact-provenance rules.
13. ADR-013 Greenfield (no v2 migration) — *decided (D2)*.

---

## 24. Suggested repository structure

**[R]** Single repo, Python backend (managed with **uv**) + React/TS frontend:

```
rtm-v3/
  docker-compose.yml            # postgres(+pgvector), redis, minio, backend, web, scraper-worker
  docker-compose.obs.yml        # optional: langfuse, prometheus, grafana (profiles)
  .env.example
  backend/
    pyproject.toml              # uv-managed; ruff, mypy, pytest config
    app/
      main.py                   # FastAPI app factory + lifespan
      core/                     # config (pydantic-settings), logging, security, db session, deps
      modules/                  # one package per bounded context
        auth/ users/ library/ books/ chapters/ reader/ audio/
        downloads/ search/ storage/ jobs/ scraping/ discovery/ summaries/
        chat/ llm/ orchestration/ tools/ observability/ admin/ notifications/
      #  each module: router.py, service.py, repository.py, schemas.py, models.py, tests/
      db/                       # SQLAlchemy base, session
      migrations/               # Alembic
    tests/                      # integration + fixtures (saved HTML for scraper contract tests)
  frontend/                     # React + Vite SPA (reuse v2 UI patterns)
    src/features/{auth,library,reader,chapters,downloads,chat,scraper,discovery,settings}
  docs/
    phase-0-discovery.md        # this file
    adr/                        # ADR-001..013
    fixtures/                   # eval datasets
  .cursor/
    rules/                      # always-on conventions (this session)
    skills/                     # invokable RTM workflows (this session)
```

---

## 25. Definition of done for the planning phase

Phase 0 is **done** when:
- [x] Stack, multi-user posture, migration, and provider decisions made → see [§0](#0-locked-decisions-phase-0-outcomes) (D1–D5).
- [x] Conventions codified as Cursor **Rules** + **Skills** (D5).
- [x] Milestones A/B/C locked (v2 parity first, chat UI placeholder in A, LLM in B+).
- [x] **Repo skeleton + Docker Compose** up (health checks green).
- [x] Milestone A feature build substantially complete (auth, library, reader, TTS/downloads, scraping, chat placeholder, UI redesign pass).
- [ ] Remaining open questions answered (esp. **Q2 languages/TTS**, **Q4 which sites + Cloudflare**, **Q5 copyright posture**, **Q7 EPUB**, **Q12 external discovery sources**).
- [x] Target **domain model (§12)** used as baseline for migrations (books, chapters, downloads, scraping, progress).

---

## Immediate next actions

1. Manual smoke-test Milestone A in Docker (scrape → read → TTS → download) and close residual UX bugs.
2. Decide EPUB (**Q7**) and Cloudflare posture (**Q4**) before calling A fully done.
3. Then Milestone B (real LLM) and C (full conversational tools).

> Milestone A feature build + UI redesign gates are green locally (ruff/mypy/pytest, eslint/tsc/vitest).
> Milestone A has **zero LLM dependency**. Reader chat is UI-only until B.
