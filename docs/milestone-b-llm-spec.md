# RTM v3 — Milestone B: LLM Foundation Spec & Decisions

> **Status:** B1 locked and implemented; B2–B4 shipped · **Updated:** 2026-07-29
>
> Companion to [phase-0-discovery.md](./phase-0-discovery.md). Phase 0 locked the
> architecture; this document locks **how** we implement the provider-agnostic LLM
> layer and slices Milestone B into shippable increments.

## Legend

| Tag | Meaning |
|-----|---------|
| **[U]** | User / phase-0 locked requirement |
| **[R]** | Recommendation locked in this document |
| **[D]** | Decision (ADR) recorded below |

---

## 1. Scope and slices

Milestone B turns the Milestone A assistant **shell** into a real, tool-using
assistant. It is delivered in four slices:

| Slice | Deliverable | Depends on |
|-------|-------------|------------|
| **B1 — Foundation (done)** | `modules/llm`, Gemini adapter, capability router, LLM tables, telemetry, contract tests | Milestone A |
| **B2 — Chat + SSE (done)** | `/api/chat`, conversation persistence, streamed assistant panel | B1 |
| **B3 — Tools + orchestrator (done)** | Registry, bounded loop, true tool streaming, budgets, full form HITL, rolling context | B2 |
| **B4 — Frontend chat (done)** | Tool/status UX, confirmation forms, choices, playback/download/settings actions | B3 |

### B1 in scope **[R]**

- `docs/milestone-b-llm-spec.md` (this file)
- `backend/app/modules/llm/` provider abstraction + Gemini adapter
- Capability-based model router with fallback / retry / timeout / circuit breaker
- Alembic migration for all conversation + telemetry tables
- `llm_execution` + `cost_record` written on every call
- Optional Langfuse tracer (no-op by default)
- Read-only `GET /api/llm/models` (auth required, no secrets)
- Offline contract tests

### B1 out of scope **[R]**

- `/api/chat`, SSE streaming of assistant turns
- Tool registry / orchestration loop
- Frontend assistant message wiring
- Embeddings / RAG / discovery
- OpenAI / Anthropic / OpenRouter / local adapters (registry stubs OK; only Gemini ships)

---

## 2. Interface contract **[U]**

All LLM access goes through `LLMProvider` in `modules/llm`. Nothing outside that
module imports litellm, instructor, or a vendor SDK.

### Protocol methods

```python
class LLMProvider(Protocol):
    @property
    def name(self) -> str: ...

    async def generate_text(self, req: GenerateTextRequest) -> GenerateTextResponse: ...
    async def stream_text(self, req: GenerateTextRequest) -> AsyncIterator[StreamChunk]: ...
    async def generate_structured_output[T](
        self, req: StructuredOutputRequest[T]
    ) -> T: ...
    async def call_tools(self, req: ToolCallingRequest) -> ToolCallingResponse: ...
    async def stream_tools(
        self, req: ToolCallingRequest
    ) -> AsyncGenerator[ToolCallingStreamChunk, None]: ...
    async def create_embeddings(self, req: EmbeddingRequest) -> EmbeddingResponse: ...
```

`create_embeddings` may raise `CapabilityNotSupportedError` until an embedding-capable
adapter is registered.

### Normalized types (owned by RTM)

`Message`, `Role` (`system` | `user` | `assistant` | `tool`), `GenerateTextRequest`,
`GenerateTextResponse`, `StreamChunk`, `ToolSpec`, `ToolCall`, `ToolCallingRequest`,
`ToolCallingResponse`, `ToolCallingStreamChunk`, `Usage` (`tokens_in`, `tokens_out`, optional `cost_usd`),
`StructuredOutputRequest[T]`, `EmbeddingRequest`, `EmbeddingResponse`.

Adapters normalize vendor quirks (tool schema, token accounting, system-prompt
semantics, streaming frames) into these types.

### Capabilities (request these, never model names) **[U]**

| Capability | Typical use |
|------------|-------------|
| `FAST_CHAT` | Default assistant replies |
| `TOOL_CALLING` | Orchestrator tool loops |
| `STRUCTURED_EXTRACTION` | instructor + pydantic schemas |
| `LONG_CONTEXT_SUMMARIZATION` | Chapter / book summaries |
| `RERANKING` | Search candidate reordering |
| `EMBEDDING` | pgvector indexing |
| `LOCAL_PRIVATE_INFERENCE` | Sensitive ops (future Ollama/vLLM) |

Callers ask `LlmService` for a **capability** (+ optional task tag and constraints).
A **model router** maps that to an ordered candidate list.

---

## 3. Model catalog & routing **[R]**

### Static registry (seeded to DB)

Code owns a static catalog in `registry.py`. On startup, `seed_llm_models()` upserts
rows into `model_provider` / `model_configuration` (same pattern as scraping sources).

**B1 default catalog:**

| Provider | Model id | Capabilities | Notes |
|----------|----------|--------------|-------|
| `gemini` | `gemini-3.5-flash-lite` | `FAST_CHAT`, `TOOL_CALLING`, `STRUCTURED_EXTRACTION` | Default free-tier model (15 RPM / 500 RPD) |
| `gemini` | `gemini-3.6-flash` | same + larger context | Fallback for harder tasks; free tier only ~20 RPD |

Domain / orchestration code **never** hardcodes these strings.

### Router behaviour

1. Filter catalog by requested capability + `supports_*` flags + `enabled`.
2. Prefer `settings.llm_model` when it matches; otherwise capability-ordered defaults.
3. For each candidate: feature-detect → call with timeout → on failure, next candidate
   (`fallback_used=true` on telemetry).
4. Per-provider **circuit breaker**: after N consecutive failures, skip provider for a
   cool-down window.
5. Bound retries: `llm_max_retries` (default 2) for transient / schema-invalid errors.

---

## 4. Data model **[U]**

One Alembic migration creates:

| Table | Purpose | Written in |
|-------|---------|------------|
| `conversations` | Chat threads (`user_id` FK, title) | B2+ |
| `conversation_messages` | Roles + content + token counts | B2+ |
| `tool_calls` | Audit of tool proposals / results | B3+ |
| `llm_executions` | Every provider call (tokens, cost, latency, status, fallback, trace_id) | **B1** |
| `cost_records` | Cost dashboards (FK → llm_execution) | **B1** |
| `model_providers` | Enabled providers + config jsonb | **B1** (seed) |
| `model_configurations` | Per-model capabilities / context / flags | **B1** (seed) |

Conventions: UUID PKs, `created_at` / `updated_at` timestamptz, ownership FKs,
indexes on FKs and hot status columns. Soft-delete not required for telemetry rows.

---

## 5. Budgets & free-tier limits **[R]**

Observed Google AI Studio free-tier caps for `gemini-3.5-flash-lite` (2026-07):

- **15 RPM**, **250K TPM**, **500 RPD**

B1 enforces:

- Per-call timeout: `llm_timeout_seconds` (default 30)
- Max output tokens: `llm_max_output_tokens` (default 2048)
- Max retries: `llm_max_retries` (default 2)

On HTTP 429 / quota errors: classify as `RateLimitError`, do **not** burn the circuit
breaker as a hard failure until retries are exhausted; surface a clear domain error.
Conversation/token budgets land in B2/B3 with the orchestrator.

`LLM_ENABLED=false` (default) → Milestone A behaviour unchanged; no provider calls.

---

## 6. Security **[U]**

- API keys only via `pydantic-settings`; never logged; never returned from HTTP.
- Keys isolated to `modules/llm` (adapters read settings; other modules call `LlmService`).
- Scraped / book / tool text is **untrusted data**: delimit clearly in prompts later
  (B2/B3); it cannot select tools or escalate.
- `internal_only` mode (future): zero external provider calls — local adapter or hard
  disable. Langfuse stays off when disabled.
- `GET /api/llm/models` requires auth and returns capability metadata only (no keys).
- Fail fast at startup **only** when `llm_enabled=true` and the configured provider key
  is missing.

---

## 7. Decision log (ADRs)

### ADR-1 — Transport: google-genai in B1; litellm when wheels available **[D]**

**Decision:** B1 implements `GeminiProvider` with the official **`google-genai`**
SDK. **litellm** remains the intended multi-vendor transport (optional extra) once
platform wheels install cleanly (current litellm releases require a Rust native
build that fails on some Windows toolchains).

**Rationale:** Ship Gemini now without blocking on litellm build tooling. Adapter
boundaries still isolate the SDK so swapping to litellm later is a one-file change.

**Escape hatch / revisit:** Prefer litellm for OpenAI/Anthropic/OpenRouter adapters;
migrate Gemini to litellm when `uv add litellm` succeeds on all dev platforms.

### ADR-2 — Structured output: instructor + pydantic **[D]**

**Decision:** `generate_structured_output` uses **instructor** with pydantic models;
bounded retry on schema-invalid responses.

**Rationale:** Phase-0 locked; single validation story with HTTP/tool schemas.

**Revisit when:** instructor cannot express a required schema and a vendor-native
structured API is clearly better for that one adapter.

### ADR-3 — Orchestration: hand-rolled loop (not LangGraph) **[D]**

**Decision:** Confirm phase-0 Q11 — **hand-rolled** orchestrator in B3. Not LangGraph
for B1–B3.

**Rationale:** Explicit budgets, HITL confirmation gates, provider-agnosticism, no
framework lock-in. Full control over SSE progress and audit.

**Revisit when:** multi-agent branching is required, durable checkpoint/resume of a
run is required, or the loop module grows past ~400 lines of real logic.

### ADR-4 — Tracing: Langfuse optional **[D]**

**Decision:** Postgres `llm_executions` + `cost_records` are the **source of truth**
for cost. Langfuse is optional behind `LANGFUSE_ENABLED` (+ compose profile later),
with a **no-op tracer** by default.

**Rationale:** Offline / `internal_only` must work without SaaS. Rich traces are nice
for debugging, not required for B1.

**Revisit when:** team needs multi-step span UI that Postgres queries cannot replace.

### ADR-5 — Model config is data **[D]**

**Decision:** Static registry in code → seed into `model_providers` /
`model_configurations`. Domain never hardcodes model names; settings only pick
defaults (`LLM_PROVIDER`, `LLM_MODEL`).

**Rationale:** Phase-0 routing requirement; swap/compare without code changes.

**Revisit when:** ops need hot-edit of catalog without redeploy (admin UI).

### ADR-6 — Default dev model & kill switch **[D]**

**Decision:**

```env
LLM_ENABLED=false          # default — A stays LLM-free
LLM_PROVIDER=gemini
LLM_MODEL=gemini-3.5-flash-lite
GEMINI_API_KEY=...         # required only when LLM_ENABLED=true
```

**Rationale:** Free tier (500 RPD) is enough for development; kill switch keeps A
parity for anyone without a key.

**Revisit when:** free-tier model id is deprecated (prefer next Flash-Lite).

---

## 8. Module layout **[R]**

```
backend/app/modules/llm/
  __init__.py
  types.py
  capabilities.py
  provider.py              # LLMProvider Protocol
  providers/
    __init__.py            # resolve by name
    gemini_provider.py     # litellm + instructor (SDK isolation)
  registry.py
  model_router.py          # NOT router.py — that is FastAPI
  service.py
  telemetry.py
  repository.py
  models.py
  schemas.py               # HTTP DTOs for GET /models
  exceptions.py
  seed.py
  router.py                # GET /api/llm/models
  tests/                   # (actual tests live under backend/tests/llm/)
```

Dependency direction: `router → service → (model_router → provider)` and
`service → telemetry → repository`. No cross-module reach into other modules'
repositories.

---

## 9. Test strategy **[R]**

All B1 tests are **offline** (mock network). Markers: `unit` / `integration`.

| Suite | Asserts |
|-------|---------|
| `test_provider_contract.py` | Normalized types per protocol method; structured output validates; tool-call parse; feature detection refuses unsupported ops |
| `test_model_router.py` | Capability order; fallback on provider error; timeout / circuit breaker |
| `test_registry.py` | Capability / context / pricing metadata coherent |
| `test_llm_telemetry.py` | Invocation writes `llm_execution` + `cost_record` (integration) |

Manual smoke (not CI): `LLM_ENABLED=true` + real key → one scripted call → row in
`llm_executions`; `LLM_ENABLED=false` → app boots as Milestone A.

---

## 10. Definition of done (B1)

- [x] This spec committed under `docs/`
- [x] `modules/llm` implements protocol + Gemini adapter + router + telemetry
- [x] Alembic migration applied and reversible
- [x] Model catalog seeded
- [x] `GET /api/llm/models` works for authenticated users
- [x] `ruff` / `mypy` / `pytest -m "unit or integration"` green
- [x] App unchanged when `LLM_ENABLED=false`

---

## 11. Follow-ups (not B1)

- B2/B3/B4 are complete; see `docs/llm-planning/README.md`.
- Milestone C next: theme/trope discovery, candidate summaries, richer grounded discuss,
  gated destructive/large actions, and an eval harness.
- Additional adapters (OpenRouter, OpenAI, Anthropic, Local)
- Compose `langfuse` profile when first needed
