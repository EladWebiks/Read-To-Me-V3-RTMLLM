# 07 — Decision log (ADRs)

> One place for every LLM/assistant architectural decision. ADR-1..6 were locked in the
> B1 spec ([milestone-b-llm-spec.md](../milestone-b-llm-spec.md) §7) and are summarized
> here; ADR-7..12 cover B3+ (some locked by maintainer 2026-07-28).

## Status key

| Status | Meaning |
|--------|---------|
| **Locked** | Decided (implemented or committed for the current phase) |
| **Proposed** | Recommended here, awaiting review before build |

---

## Locked in B1 (recap)

### ADR-1 — Transport: `google-genai` now, litellm later — **Locked**
Gemini adapter uses the official `google-genai` SDK; litellm remains the intended
multi-vendor transport once wheels install cleanly.

### ADR-2 — Structured output: instructor + pydantic — **Locked**
`generate_structured_output` uses instructor with pydantic; bounded retry on
schema-invalid responses.

### ADR-3 — Orchestration: hand-rolled loop (not LangGraph) — **Locked (reaffirmed)**
Hand-rolled orchestrator for B3. North-star flows need tools + form HITL + a pausable
loop; LangGraph does not replace those. Revisit: multi-agent branching, durable
checkpoint/resume across restarts, or loop >~400 lines of real control logic. Detail in
[03-orchestration.md](./03-orchestration.md) §1 and [00-north-star.md](./00-north-star.md).

### ADR-4 — Tracing: Langfuse optional; Postgres is source of truth — **Locked**
`llm_executions` + `cost_records` are authoritative; Langfuse off-by-default. Detail in
[05-observability.md](./05-observability.md).

### ADR-5 — Model config is data — **Locked**
Static registry seeds DB; domain never hardcodes model names.

### ADR-6 — Default dev model & kill switch — **Locked**
`LLM_ENABLED=false` by default; `gemini-3.5-flash-lite`; key only when enabled.

---

## B3+ decisions

### ADR-7 — Split `tools` and `orchestration` into two modules — **Proposed**
**Decision:** `tools/` = catalog + registry; `orchestration/` = loop/budgets/HITL/tracing.
**Rationale:** isolate unit tests; adding a tool never touches the engine.
**Alternatives:** one combined module.
**Revisit:** if the registry stays trivially small.

### ADR-8 — HITL via SSE interrupt + `POST /confirm` resume — **Locked**
**Decision:** gated tools emit `confirmation_request` (optional `form`), end the SSE
response in `awaiting_confirmation`, resume via
`POST /api/chat/{id}/confirm { call_id, approved, values? }` with a new SSE stream
stitched by `run_id`/`call_id`.
**Rationale:** no long-lived socket; survives reconnects; fits form submit.
**Alternatives:** websocket (deferred).
**Revisit:** live bidirectional UX or many concurrent runs.

### ADR-9 — Confirmations persist on `tool_call` — **Locked**
**Decision:** `tool_call` statuses `pending_confirmation → confirmed/rejected/expired`;
store proposal + **final merged input** and `confirmed_by_user`.
**Rationale:** durable; one audit row; confirmation-rate metric.
**Alternatives:** separate `confirmations` table.
**Revisit:** only if workflows need multi-step approval chains beyond one form.

### ADR-10 — Budgets are explicit settings enforced by the loop — **Proposed**
**Decision:** iteration/external-call/token/cost/wall-clock caps per run
([03](./03-orchestration.md) §3).
**Rationale:** no uncontrolled agent loops [U]; free-tier predictability.
**Revisit:** tune from telemetry; per-user overrides later.

### ADR-11 — Orchestration runs in-process for B3; arq worker deferred — **Proposed**
**Decision:** loop behind the SSE request in-process for B3.
**Rationale:** simplest for single-user; Redis pub/sub later if needed.
**Revisit:** event-loop blocking or concurrency pressure.

### ADR-12 — HITL supports structured forms + clarify/choice is separate — **Locked**
**Decision:** `confirmation_required` tools may declare `confirmation_schema` for
user-editable fields (e.g. start chapter, chapter count). Clarify / multi-choice is a
**non-executing** UX (`choice_request` or prose), never a substitute for the gate.
**Rationale:** matches north-star import flow ([00](./00-north-star.md),
[04](./04-hitl.md)).
**Alternatives:** binary-only HITL (rejected — too weak for scrape params).
**Revisit:** if forms need conditional fields or multi-page wizards.

### ADR-13 — Persist LLM book summaries for search + reuse — **Locked (design)**
**Decision:** Milestone C **must** ship a `book_summaries` (or equivalent) table and
tools to read/ensure summaries. Summaries are a cache of derived data with
`content_hash` / `prompt_version` invalidation. Search prefers summary/metadata, then
falls back to chapter FTS. Generate on demand (or after scrape), not bulk by default.
**Rationale:** repeated “what’s this about?” and theme Q&A should not re-burn tokens or
re-scan full chapter text every turn; title-only search is insufficient.
**Alternatives:** (a) always re-summarize live — rejected (cost/latency);
(b) chapter FTS only — rejected as sole strategy (poor for overview questions);
(c) embeddings-only — deferred until after summary cache proves insufficient.
**Revisit:** shared/global summaries across users; embedding index over summary text.
**Detail:** [06-roadmap-and-sequencing.md](./06-roadmap-and-sequencing.md) §4a.

### ADR-14 — UI route context + client navigate actions (not LLM-driven refresh) — **Locked (design)**
**Decision:** B4 ships (1) **`ui_context` on chat turns** — current path plus optional
`book_id` / `chapter_id` when in the reader — injected as delimited **data** for
grounding; (2) **client-side list refresh** via React Query invalidation on relevant
`tool_result`s (e.g. scrape); (3) **navigate affordances** (chip/link or auto-nav)
driven by tool client-action payloads / FE policy — same pattern as `play_chapter`.
The model must **not** be the mechanism that refreshes SPA state.
**Rationale:** page awareness makes replies useful; SPA refresh is deterministic
infrastructure; navigate suggestions need a controlled client surface, not prose hope.
**Alternatives:** (a) no context — rejected (generic answers); (b) model invents
"refresh/go to scraper" as the only UX — rejected (unreliable); (c) full agent
control of routing — rejected (unsafe / overbuilt).
**Revisit:** richer context (selected text, visible job id) once basic route context
proves useful.
**Detail:** [01-architecture.md](./01-architecture.md) §7, [06](./06-roadmap-and-sequencing.md) §3.

---

## Change process

- Add a new ADR here (numbered, with Decision / Rationale / Alternatives / Revisit).
- If it changes a `[U]`/phase-0 item, update [phase-0-discovery.md](../phase-0-discovery.md)
  too. If it changes B1 behavior, note it against the B1 spec.
- Flip **Proposed → Locked** when the implementing slice merges (or when the maintainer
  locks the design before build, as with ADR-3/8/9/12).
