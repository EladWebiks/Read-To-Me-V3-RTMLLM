# 07 — Decision log (ADRs)

> One place for every LLM/assistant architectural decision. ADR-1..6 were locked in the
> B1 spec ([milestone-b-llm-spec.md](../milestone-b-llm-spec.md) §7) and are summarized
> here for the reviewer; ADR-7..11 are new decisions for B3+ proposed by these planning
> docs.

## Status key

| Status | Meaning |
|--------|---------|
| **Locked** | Decided and implemented (or committed for the current slice) |
| **Proposed** | Recommended here, awaiting review before B3 build |

---

## Locked in B1 (recap)

### ADR-1 — Transport: `google-genai` now, litellm later — **Locked**
Gemini adapter uses the official `google-genai` SDK; litellm remains the intended
multi-vendor transport once wheels install cleanly. Adapter boundary isolates the SDK.

### ADR-2 — Structured output: instructor + pydantic — **Locked**
`generate_structured_output` uses instructor with pydantic; bounded retry on
schema-invalid responses.

### ADR-3 — Orchestration: hand-rolled loop (not LangGraph) — **Locked (B1–B3)**
Hand-rolled orchestrator for explicit budgets, HITL, provider-agnosticism, and SSE/audit
control. Revisit triggers: multi-agent branching, durable checkpoint/resume, or loop
>~400 lines. Detail in [03-orchestration.md](./03-orchestration.md) §1.

### ADR-4 — Tracing: Langfuse optional; Postgres is source of truth — **Locked**
`llm_executions` + `cost_records` are authoritative; Langfuse is off-by-default behind
`LANGFUSE_ENABLED` with a no-op tracer. Detail in [05-observability.md](./05-observability.md).

### ADR-5 — Model config is data — **Locked**
Static registry in code seeds `model_providers` / `model_configurations`; domain never
hardcodes model names; settings only pick defaults.

### ADR-6 — Default dev model & kill switch — **Locked**
`LLM_ENABLED=false` by default (Milestone A parity); `gemini-3.5-flash-lite` default;
`GEMINI_API_KEY` required only when enabled.

---

## Proposed for B3+ (for review)

### ADR-7 — Split `tools` and `orchestration` into two modules — **Proposed**
**Decision:** `tools/` is the declarative catalog + registry; `orchestration/` is the
generic loop/budgets/HITL/tracing. The orchestrator depends on `tools` + `llm` and knows
no specific tool.
**Rationale:** tools are unit-testable in isolation; the loop stays generic; adding a
tool never touches the engine (see the `add-llm-tool` skill).
**Alternatives:** one combined module (simpler, but couples the loop to tool internals).
**Revisit:** if the registry stays trivially small, merging is cheap.

### ADR-8 — HITL via SSE interrupt + `POST /confirm` resume — **Proposed [Q3]**
**Decision:** gated tools emit `confirmation_request`, end the current SSE response with
the run `awaiting_confirmation`, and resume via `POST /api/chat/{id}/confirm` which opens
a new SSE stream stitched by `run_id`/`call_id`.
**Rationale:** avoids holding a socket open; survives reconnects; single-user friendly.
**Alternatives:** websocket (bidirectional but heavier).
**Revisit:** if we need live bidirectional UX or many concurrent runs.

### ADR-9 — Confirmations persist on `tool_call` (`pending_confirmation`) — **Proposed**
**Decision:** reuse `tool_call` with statuses `pending_confirmation → confirmed/rejected/
expired`, storing frozen input and `confirmed_by_user`.
**Rationale:** durable across refresh; one audit row per action; feeds confirmation-rate
metric. **Alternatives:** a separate `confirmations` table (more schema, little gain).
**Revisit:** if confirmations need richer workflow than a single approve/reject.

### ADR-10 — Budgets are explicit settings enforced by the loop — **Proposed**
**Decision:** iteration/external-call/token/cost/wall-clock caps are settings enforced
per run (defaults in [03](./03-orchestration.md) §3); exceeding any ends the run with a
user-visible reason.
**Rationale:** "no uncontrolled agent loops" [U]; predictable cost on free tier.
**Revisit:** tune defaults from real telemetry; per-user overrides later.

### ADR-11 — Orchestration runs in-process for B3; arq worker deferred — **Proposed**
**Decision:** run the loop behind the SSE request in-process for B3 (single-user).
**Rationale:** simplest correct thing; avoids Redis pub/sub plumbing before it's needed.
**Alternatives:** run in an arq worker and stream via Redis (phase-0 §7's pattern).
**Revisit:** concurrency/robustness pressure, or long runs blocking the event loop.

---

## Change process

- Add a new ADR here (numbered, with Decision / Rationale / Alternatives / Revisit).
- If it changes a `[U]`/phase-0 item, update [phase-0-discovery.md](../phase-0-discovery.md)
  too. If it changes B1 behavior, note it against the B1 spec.
- Flip **Proposed → Locked** when the implementing slice merges.
