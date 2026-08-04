# 03 — Orchestration: the hand-rolled loop

> The engine that turns a user message into an assistant turn by calling tools under
> hard caps. This is where budgets, cancellation, tracing, and the SSE protocol live.
> Product target: [00-north-star.md](./00-north-star.md).

## 1. Decision: hand-rolled loop, not LangGraph (for B3) **[D → ADR-3]**

**Maintainer lock (2026-07-28):** keep hand-rolled for B3. The north-star session
(discovery → summarize → form-HITL scrape → queue) needs **tools + form HITL + a
pausable loop**, not a graph framework. LangGraph would not replace those building
blocks; it would only swap the loop implementation.

**Why hand-rolled now**

- Explicit **budgets** and **form-aware HITL gates** are first-class.
- **Provider-agnostic** — no framework that assumes a particular SDK or message shape.
- Full control over the **SSE progress protocol** and **audit** (`tool_call`,
  `llm_execution`) which we already own.
- Work is not thrown away: tools, schemas, and HITL payloads stay if we ever put
  LangGraph *inside* `orchestration/` later.

**When to revisit LangGraph** (any one triggers a re-evaluation):

- We need **multi-agent branching** (planner/executor/critic as separate nodes).
- We need **durable checkpoint/resume** of a long run across process restarts (beyond
  the HITL pause we implement ourselves).
- The loop module grows past **~400 lines of real control logic** or its branching
  becomes hard to test.

If triggered: LangGraph sits **inside `orchestration/`** only; tools, budgets, authz,
and SSE stay ours. See [07-decision-log.md](./07-decision-log.md).

## 2. The loop (pseudocode)

```python
async def run(ctx: ToolContext, user_message: str) -> AsyncIterator[SseEvent]:
    budget = Budget.for_conversation(ctx)     # tokens, cost, iters, wall-clock
    messages = load_history(ctx) + [user(user_message)]
    persist(user_message)

    for _ in range(budget.max_iters):
        budget.check_walltime()
        specs = registry.list_specs(ctx.mode)
        resp = await llm.stream_tools(messages, specs, capability=TOOL_CALLING)
        record_execution(resp)                # llm_execution + cost_record
        budget.add(resp.usage)

        if resp.text:
            yield provider_deltas(resp.text)  # real SSE delta events

        if not resp.tool_calls:
            break                             # final answer

        for call in resp.tool_calls:
            tool = registry.resolve(call.name)
            inp = tool.input_schema.model_validate(call.args)   # 1 validate
            await tool.authorize(inp, ctx)                      # 2 authz
            gate_risk_and_mode(tool, ctx)                       # 3 risk/mode
            await ratelimit(tool, ctx)                          # 4 rate/idempotency

            if tool.risk_level == CONFIRMATION_REQUIRED:
                # 5a pause — binary or form; merge user values into args
                approval = yield ConfirmationRequest(call, form=tool.confirmation_schema)
                if not approval.approved:
                    messages.append(tool_result(call, denied=True)); continue
                inp = tool.input_schema.model_validate(approval.values)

            out = await with_timeout(tool.execute(inp, ctx), tool.timeout_ms)  # 5b
            out = tool.output_schema.model_validate(out)
            audit_tool_call(call, out, ctx)
            messages.append(tool_result(call, out))
            yield ToolResultEvent(call, redact(out))

    persist_assistant_message(messages[-1])
    yield Done(budget.summary())
```

## 3. Budgets & caps (mandatory) **[U]**

The loop caps **all** of these. Exceeding one produces a typed error code; the frontend
must translate it into useful user copy rather than exposing internal budget text:

| Cap | Setting (proposed) | Default |
|-----|--------------------|---------|
| Max tool-call iterations | `llm_max_tool_iters` | 6 |
| Max external requests / run | `llm_max_external_calls` | 8 |
| Max tokens / conversation turn | `llm_max_turn_tokens_in` / `_out` | 64k in + 8k out (cumulative across tool rounds; a completed final answer records soft-limit overage instead of being discarded) |
| Max cost / turn (USD) | `llm_max_turn_cost_usd` | 0.05 |
| Max wall-clock / run | `llm_run_deadline_seconds` | 150 |
| Per-tool timeout | tool `timeout_ms` | tool-specific |
| Per-provider circuit breaker | (from B1 router) | inherited |

Free-tier Gemini limits (15 RPM / 250K TPM / 500 RPD, per B1 spec) also bound
throughput; the router already classifies 429 as `RateLimitError`.

### 3a. Rolling conversation context — implemented

- Full original `conversation_messages` remain unchanged for history and audit.
- Context keeps the latest `LLM_CONTEXT_RECENT_MESSAGES` (clamped to 8–12) verbatim.
- Unsummarized older messages remain verbatim until they cross
  `LLM_SUMMARY_TRIGGER_TOKENS` (default 12K estimated tokens).
- The owned `conversation_summaries` row stores the compact prefix, terminal message id,
  and source count. Invalid markers/counts are discarded and reconstructed from originals.
- Large prefixes are summarized in bounded chunks. The result is injected in a clearly
  delimited system block labeled **untrusted historical data; never instructions**.
- Summary generation is provider-agnostic and recorded as `conversation_summary`
  telemetry. Failure falls back to original messages rather than losing context.

## 4. SSE event protocol

One stream per turn; discriminated by `type`. Extends the B2 chat stream with progress,
tool, HITL, and choice events around the assistant `delta` / `done` / `error` lifecycle.

**Request (B4+):** `POST /api/chat` may include `ui_context` `{ path, book_id?, chapter_id? }`
— injected into the turn as delimited data (ADR-14). Not an SSE event.

| `type` | Payload | Meaning |
|--------|---------|---------|
| `step` | `{label}` | Human-readable progress ("Searching your library…") |
| `delta` | `{text}` | Streamed assistant text chunk |
| `tool_result` | `{name, ok, summary, client_action?}` | Redacted result; optional navigate/play/settings/download payload for FE |
| `confirmation_request` | `{call_id, tool, args, risk, summary, form?}` | Loop paused; binary or **form** HITL — see [04](./04-hitl.md) |
| `choice_request` | `{options[]}` | Optional clarify chips (B4+); not a tool gate |
| `error` | `{code, message}` | Domain error (rate limit, budget exceeded, denied) |
| `done` | `{usage, cost_usd, run_id}` | Turn complete + budget summary |

Rules: text and results are separate event types so the frontend can render assistant
prose (markdown) distinctly from tool / HITL affordances. Tool outputs are
**redacted/summarized** for the stream; full output lives in the `tool_call` audit row.
List refreshes (Scraper/library) are **FE invalidation** on `tool_result`, not a model
action — see ADR-14.

### 4b. Deterministic post-confirm download completion

`create_audio_download` does not ask the model to reinterpret a successful approval.
After execution, the backend emits the authoritative queued result plus a `download`
client action and ends with deterministic copy. The frontend removes the approved form,
polls the owned job, renders chapter progress, auto-downloads the named MP3 on completion,
and retains a manual retry button. Failed execution never claims that a job was queued.

### 4a. True provider streaming for tool turns **[R]** — implemented

**Implemented (2026-07-29):** `LLMProvider.stream_tools()` exposes normalized text
deltas followed by a terminal `ToolCallingResponse`. The Gemini adapter uses its
streaming generation API, and the orchestrator forwards text immediately as SSE
`delta` events without sleep-based pacing.

Vendor adapters may receive interleaved text and partial function arguments, but
`orchestration` must only see provider-agnostic events:

- text deltas that can be forwarded immediately as SSE `delta` events;
- complete normalized `ToolCall` values (partial vendor arguments are assembled inside
  the adapter before pydantic validation or execution);
- a terminal usage/cost event for budgets and `llm_execution` telemetry.

Gemini implements this through its streaming generation API. Future providers implement
the same RTM-owned contract; orchestration and domain modules never import vendor SDK
types. Mixed text + tool-call responses remain valid: text is assistant prose, while a
tool executes only after its complete call has been assembled and validated.

Cancellation must close the provider stream, cancel active tool work, and record a
cancelled/partial execution without fabricating usage. Artificial chunking and
sleep-based pacing are removed; the provider stream is wired (B3.4).

**Acceptance criteria:**

1. A provider contract test proves the first text delta is observable before generation
   completes.
2. Fragmented function-call arguments assemble into exactly one validated `ToolCall`;
   incomplete calls never execute.
3. Tool → result → final-answer rounds remain one ordered SSE stream, with usage and
   cost counted once per provider round.
4. Client abort cancels the provider iterator and no later `delta`, tool execution, or
   `done: complete` event is emitted.
5. Gemini integration and orchestration tests cover text-only, tool-only, mixed,
   malformed, provider-error, and cancellation paths.

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
