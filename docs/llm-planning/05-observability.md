# 05 — Observability & Langfuse

> Postgres is the **source of truth** for cost and audit. Langfuse is an optional,
> off-by-default tracing layer for debugging multi-step runs. See B1 spec ADR-4.

## 1. Source of truth: Postgres **[D → ADR-4]**

Every provider call already writes (B1):

- `llm_executions` — `provider, model, tokens_in, tokens_out, cost, latency_ms,
  status, fallback_used, trace_id`.
- `cost_records` — FK → `llm_execution`, for cost dashboards.

B3 adds:

- `tool_calls` — per tool: `input, output, status, duration_ms, risk_level,
  confirmed_by_user, error` (see [02](./02-tools.md) / [04](./04-hitl.md)).

**Rationale:** offline / `internal_only` deployments must fully work without any SaaS.
Cost, tool success-rate, and confirmation-rate are all queryable from Postgres. This is
non-negotiable and does not depend on Langfuse being present.

## 2. Metrics we can answer from Postgres (phase-0 §17)

| Question | Source |
|----------|--------|
| Tokens / cost per model, per day | `llm_executions` + `cost_records` |
| Latency p50/p95 per model | `llm_executions.latency_ms` |
| Fallback rate | `llm_executions.fallback_used` |
| Tool success/failure rate, per-tool latency | `tool_calls.status`, `duration_ms` |
| Confirmation rate | `tool_calls.confirmed_by_user` |
| Cost regression over time | `cost_records` (eval harness) |

## 3. Langfuse: optional tracing **[D → ADR-4]**

- Behind `LANGFUSE_ENABLED` (default **false**) with a **no-op tracer** by default —
  already scaffolded in `modules/llm/telemetry.py`.
- When enabled: a run's `run_id` (from [03](./03-orchestration.md)) becomes a **trace**;
  each LLM call and tool execution becomes a **span** with token/cost/latency.
- Compose runs it behind a **profile** so `internal_only` / offline never requires it
  (phase-0 §16 / §17).

### What Langfuse adds that Postgres queries don't

- A **timeline UI** across the steps of one run (LLM → tool → LLM → tool …).
- Prompt/response inspection and diffing while debugging tool-selection.
- Grouping and tagging of eval datasets.

### What it does **not** replace

- The authoritative cost/audit rows. Langfuse is a lens, not the ledger.

## 4. When to turn Langfuse on **[Q2]**

Two reasonable positions for the reviewer:

- **Enable at B3 start** — the moment there are multi-step runs, the timeline UI pays
  for itself when debugging why a tool was/wasn't chosen. Cost: run a Langfuse
  container (compose profile) in dev.
- **Defer** — stay Postgres-only until a concrete debugging pain appears; keep dev
  footprint minimal.

**Recommendation [R]:** enable the Langfuse **compose profile in dev only** at B3, keep
it **off** in `internal_only`/prod-offline. Low cost, high debugging value exactly when
the loop gets complex.

## 5. Data minimization & privacy (phase-0 §17, `60-security`)

- Send the model only what a task needs; prefer `LOCAL_PRIVATE_INFERENCE` for sensitive
  ops (future).
- Langfuse stores prompts/responses — when enabled, be mindful it may capture book/user
  text. Keep it dev-only unless a retention review says otherwise, and never point it at
  a shared SaaS project for `internal_only` data.
- Never log secrets or full tool outputs that contain other-user data (they don't, by
  the tool contract, but redact defensively in stream events).

## 6. Evaluations (phase-0 §18) — Milestone C

Repeatable datasets (not vibes) for: **tool-selection accuracy**, structured-output
validity, summary quality, search relevance, plus a **cost regression** test. Adapt the
LLM project's `research/eval` approach. Langfuse datasets are a convenience here but the
pass/fail gate reads from Postgres cost/telemetry so it works offline in CI.
