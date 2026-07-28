# 06 — Roadmap & sequencing

> The concrete build order from here, with acceptance criteria per slice. "What order
> to implement stuff." Each slice must pass the quality gates in rule `85` before it is
> "done" (ruff + mypy + pytest backend; eslint + prettier + tsc + vitest frontend).

## 1. Big picture

```
B1 (done) ─► B2 (done) ─► B2.5 UX (done) ─► B3 tools+loop ─► B4 tool UX ─► C full assistant
```

- **B** = wire the chat shell to a real, tool-using assistant with budgets + HITL.
- **C** = confirmation-gated scrape/download, summaries, richer Q&A, discovery/RAG.

## 2. B3 — tools + orchestrator (next)

Delivered as small vertical slices so the loop is exercised end-to-end early.

### B3.0 — engine skeleton
- New modules `orchestration/` and `tools/` (router → service → registry → tool).
- `ToolContext`, execution contract, `tool_call` audit, budgets/caps from
  [03](./03-orchestration.md).
- Wire `orchestration.service` into the existing `/api/chat` SSE path (replaces the
  tool-less B2 reply with the loop; tool-less answers still work when no tool fires).
- **2 read-only tools:** `search_user_books`, `get_book_details`.
- **Accept:** a chat that asks "what books do I have?" triggers `search_user_books`,
  streams a `tool_result` + answer, writes `tool_call` + `llm_execution`; all caps
  enforced; offline tests green.

### B3.1 — full read-only tool set (Batch 1)
- `get_reading_progress`, `get_recently_read_chapters`, `list_available_chapters`,
  `get_chapter_content`, `search_library_content`, `get_download_status`.
- **Accept:** authz matrix test per tool (own vs other user), schema-rejection test,
  injection test (tool text is inert).

### B3.2 — low-risk actions (Batch 2)
- `play_chapter`, `resume_book`, `create_chapter_download` (single, idempotent).
- **Accept:** state changes are owned + reversible; idempotency prevents duplicate jobs;
  audited.

### B3.3 — HITL gate + first gated tool
- Confirmation lifecycle from [04](./04-hitl.md): `confirmation_request` event,
  `POST /confirm`, pending `tool_call`, resume.
- First `confirmation_required` tool: `scrape_book_range`.
- **Accept:** gated tool never runs without recorded confirmation; reject/expire paths
  clean; args immutable across approval.

### B3 exit criteria
- Loop is bounded, cancellable, traced (`run_id`).
- Read-only + low-risk tools live; one HITL tool proven end-to-end (backend).
- Langfuse compose profile available in dev (off by default) — see [05](./05-observability.md).

## 3. B4 — frontend chat for tools

- Render `step` / `tool_result` events distinctly from assistant prose (prose stays
  bubble-less markdown; tool + HITL + errors get bubbles/cards — matches current UX).
- HITL approve/decline card ([04](./04-hitl.md) §5).
- Cost/status affordances **[Q4]** (turn cost meter — user-visible or internal only?).
- **Accept:** a full turn with a tool call and a confirmation renders correctly, is
  cancellable, and shows a final state; eslint/tsc/build/tests green.

## 4. Milestone C — full assistant

Ordered by dependency and value:

1. **Confirmation-gated expensive tools:** `scrape_full_book`, range/full downloads,
   `retry_failed_job`, destructive `delete_book`/`overwrite_chapters`.
2. **Summaries:** chapter/book summarization via `LONG_CONTEXT_SUMMARIZATION`
   capability + `instructor` structured output; persisted for reuse.
3. **Richer library Q&A / "discuss books":** grounded answers over the user's own
   content.
4. **Discovery + RAG (if still desired):** pgvector embeddings (`EMBEDDING` capability),
   `discovery` module, internal-first search then gated external sources, provenance +
   confidence persisted so future searches are internal (phase-0 §16).
5. **Eval harness** ([05](./05-observability.md) §6): tool-selection, structured-output,
   summary quality, cost regression.

## 5. Cross-cutting, do-once-then-reuse

- **Prompt architecture:** authoritative system prompt; untrusted content clearly
  delimited as data; tool schemas as the only action surface. Lock this in B3.0 and
  reuse.
- **Rate limiting:** per-user/per-tool/per-source — add the primitive in B3.0, apply per
  tool thereafter.
- **Central fetcher / SSRF guard:** required before any `touches_external` tool (B3.3).

## 6. Dependencies at a glance

| Slice | Requires |
|-------|----------|
| B3.0 | B2 chat/SSE, B1 provider (`TOOL_CALLING`) |
| B3.1–B3.2 | B3.0 engine + domain services |
| B3.3 | central fetcher/SSRF, HITL transport |
| B4 | B3 SSE event types |
| C (discovery) | pgvector, `discovery` module, external-source review [Q12] |

## 7. Definition of done reminder (rule 85)

Every slice: backend `ruff`/`mypy`/`pytest -m "unit or integration"` green; frontend
`lint`/`format`/`build`(tsc)/`test` green. Frontend size limits (max-lines 110,
max-lines-per-function 60, max-depth 3) apply — keep splitting hooks/components as we did
for the chat UI.
