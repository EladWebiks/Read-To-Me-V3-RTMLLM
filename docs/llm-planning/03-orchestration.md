# 03 — Orchestration: the hand-rolled loop

> The engine that turns a user message into an assistant turn by calling tools under
> hard caps. This is where budgets, cancellation, tracing, and the SSE protocol live.

## 1. Decision: hand-rolled loop, not LangGraph (for B3) **[D → ADR-3]**

Phase-0 Q11 and the B1 spec (ADR-3) locked a **hand-rolled** orchestrator for B1–B3.
Restated here with the criteria a reviewer should weigh:

**Why hand-rolled now**

- Explicit **budgets** (tokens / cost / iterations / wall-clock) and **HITL gates** are
  first-class, not bolted onto a framework's control flow.
- **Provider-agnostic** — no framework that assumes a particular SDK or message shape.
- Full control over the **SSE progress protocol** and **audit** (`tool_call`,
  `llm_execution`) which we already own.
- No framework lock-in while the loop is small (a few hundred lines).

**When to revisit LangGraph** (any one triggers a re-evaluation):

- We need **multi-agent branching** (planner/executor/critic as separate nodes).
- We need **durable checkpoint/resume** of a long run across process restarts (beyond
  the single HITL pause we implement ourselves).
- The loop module grows past **~400 lines of real control logic** or its branching
  becomes hard to test.

If triggered: LangGraph would sit **inside `orchestration/`** only; tools, budgets,
authz, and the SSE protocol stay ours. It never leaks into domain code. See
[07-decision-log.md](./07-decision-log.md).

## 2. The loop (pseudocode)

```python
async def run(ctx: ToolContext, user_message: str) -> AsyncIterator[SseEvent]:
    budget = Budget.for_conversation(ctx)     # tokens, cost, iters, wall-clock
    messages = load_history(ctx) + [user(user_message)]
    persist(user_message)

    for _ in range(budget.max_iters):
        budget.check_walltime()
        specs = registry.list_specs(ctx.mode)
        resp = await llm.call_tools(messages, specs, capability=TOOL_CALLING)
        record_execution(resp)                # llm_execution + cost_record
        budget.add(resp.usage)

        if resp.text:
            yield from stream_text(resp.text) # SSE step / token events

        if not resp.tool_calls:
            break                             # final answer

        for call in resp.tool_calls:
            tool = registry.resolve(call.name)
            inp = tool.input_schema.model_validate(call.args)   # 1 validate
            await tool.authorize(inp, ctx)                      # 2 authz
            gate_risk_and_mode(tool, ctx)                       # 3 risk/mode
            await ratelimit(tool, ctx)                          # 4 rate/idempotency

            if tool.risk_level == CONFIRMATION_REQUIRED:
                approval = yield ConfirmationRequest(call)      # 5a pause (HITL)
                if not approval.approved:
                    messages.append(tool_result(call, denied=True)); continue

            out = await with_timeout(tool.execute(inp, ctx), tool.timeout_ms)  # 5b
            out = tool.output_schema.model_validate(out)
            audit_tool_call(call, out, ctx)
            messages.append(tool_result(call, out))
            yield ToolResultEvent(call, redact(out))

    persist_assistant_message(messages[-1])
    yield Done(budget.summary())
```

## 3. Budgets & caps (mandatory) **[U]**

The loop must cap **all** of these; exceeding any one ends the run with a clear,
user-visible reason:

| Cap | Setting (proposed) | Default |
|-----|--------------------|---------|
| Max tool-call iterations | `llm_max_tool_iters` | 6 |
| Max external requests / run | `llm_max_external_calls` | 3 |
| Max tokens / conversation turn | `llm_max_turn_tokens` | 8k in + 2k out |
| Max cost / turn (USD) | `llm_max_turn_cost_usd` | 0.05 |
| Max wall-clock / run | `llm_run_deadline_seconds` | 60 |
| Per-tool timeout | tool `timeout_ms` | tool-specific |
| Per-provider circuit breaker | (from B1 router) | inherited |

Free-tier Gemini limits (15 RPM / 250K TPM / 500 RPD, per B1 spec) also bound
throughput; the router already classifies 429 as `RateLimitError`.

## 4. SSE event protocol

One stream per turn; discriminated by `type`. Extends the B2 chat stream (which today
only emits `token` / `done` / `error`).

| `type` | Payload | Meaning |
|--------|---------|---------|
| `step` | `{label}` | Human-readable progress ("Searching your library…") |
| `token` | `{text}` | Streamed assistant text chunk |
| `tool_result` | `{name, ok, summary}` | Redacted result of a tool call |
| `confirmation_request` | `{call_id, tool, args, risk}` | Loop paused; awaiting approval |
| `error` | `{code, message}` | Domain error (rate limit, budget exceeded, denied) |
| `done` | `{usage, cost_usd, run_id}` | Turn complete + budget summary |

Rules: text and results are separate event types so the frontend can render assistant
prose (markdown) distinctly from tool affordances. Tool outputs are **redacted/summarized**
for the stream; full output lives in the `tool_call` audit row.

## 5. Cancellation

- Client aborts the `fetch` → server sees disconnect → orchestrator cancels the current
  tool task and stops the loop; a partial assistant message may be persisted.
- A `POST /api/chat/{id}/cancel` (or abort on the SSE request) is the explicit path.
- In-flight external calls honor their `timeout_ms`; the run deadline is the backstop.

## 6. Tracing

- Each run gets a `run_id` (the trace id). It is written to `llm_execution.trace_id`,
  `tool_call`, and returned in the `done` event.
- If Langfuse is enabled ([05](./05-observability.md)), `run_id` maps to a trace and
  each LLM/tool step to a span. If disabled, Postgres rows are the full record.

## 7. Where it runs

Phase-0 §7 recommends running orchestration so the event loop stays free. For B3 the
loop runs **in-process** behind the SSE request (simplest, works for single-user). If
throughput/robustness demands it, move the run to an **arq worker** and stream events
back via Redis pub/sub — deferred until needed (a revisit trigger, not a B3 task).
