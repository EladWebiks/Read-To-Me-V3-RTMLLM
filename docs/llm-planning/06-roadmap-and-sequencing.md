# 06 — Roadmap & sequencing

> The concrete build order from here, with acceptance criteria per slice. "What order
> to implement stuff." Aligns with [00-north-star.md](./00-north-star.md). Each slice
> must pass the quality gates in rule `85` before it is "done".

## 1. Big picture

```
B1 (done) ─► B2 (done) ─► B2.5 (done) ─► B3 (done) ─► B4 (done) ─► C (in progress)
```

- **B** = tool-using assistant with budgets + **form HITL** spine.
- **C** = discovery → summarize → import/scrape with forms; discuss owned books; RAG as needed.

Hand-rolled loop stays (ADR-3). We are not waiting on LangGraph to grow toward the
canonical session.

## 2. B3 — tools + orchestrator — **done**

Delivered as small vertical slices so the loop is exercised end-to-end early.

### B3.0 — engine skeleton — **done**
- New modules `orchestration/` and `tools/` (router → service → registry → tool).
- `ToolContext`, execution contract, `tool_call` audit, budgets/caps from
  [03](./03-orchestration.md).
- Wire `orchestration.service` into the existing `/api/chat` SSE path (replaces the
  tool-less B2 reply with the loop; tool-less answers still work when no tool fires).
- Design SSE event types including **form-capable** `confirmation_request` (implement
  resume path fully in B3.3; stub types OK in B3.0).
- **2 read-only tools:** `search_user_books`, `get_book_details`.
- **Accept:** a chat that asks "what books do I have?" triggers `search_user_books`,
  streams a `tool_result` + answer, writes `tool_call` + `llm_execution`; all caps
  enforced; offline tests green.

### B3.1 — full read-only tool set (Batch 1) — **done**
- `get_reading_progress`, `get_recently_read_chapters`, `list_available_chapters`,
  `get_chapter_content`, `search_library_content`, `get_download_status`.
- **Accept:** authz matrix test per tool (own vs other user), schema-rejection test,
  injection test (tool text is inert).

### B3.2 — low-risk actions (Batch 2) — **done**
- `play_chapter`, `resume_book`, `create_chapter_download` (single, idempotent), and
  allowlisted reversible `update_ui_settings`.
- `play_chapter` / `resume_book` update reading progress and return a play client action;
  B4 now starts TTS after navigation, including same-route requests and autoplay fallback.
- **Accept:** state changes are owned + reversible; idempotency prevents duplicate jobs;
  audited.

### B3.3 — form HITL + first gated tool — **done (backend)**
- Confirmation lifecycle from [04](./04-hitl.md): `confirmation_request` with optional
  `form`, `POST /api/chat/{id}/confirm { call_id, approved, values? }`, pending `tool_call`,
  resume SSE.
- First `confirmation_required` tool: `scrape_book_range` with
  `start_chapter` + `chapter_count` (null = entire book).
- Requires `LLM_ASSISTANT_MODE=external_allowed` for the model to see scrape tools.
- Form UI cards are **B4**; confirm API is usable now (e.g. curl / API client).
- **Accept:** gated tool never runs without recorded confirmation; form merge +
  re-validation; reject/expire paths clean; args immutable except via submitted values.

### B3.4 — true provider token streaming — **done**
- Added a provider-agnostic tool-stream contract alongside `call_tools`: immediate text
  deltas, complete normalized tool calls, and terminal usage/cost.
- Implemented Gemini streaming tool calls; partial vendor function arguments assemble
  inside the adapter before validation.
- Real provider text deltas flow through SSE; completed-text slicing, artificial delays,
  and fake typing were removed from the backend.
- Ordered tool rounds, budgets, telemetry, HITL pause/resume, and cancellation are preserved.
- **Accept:** first text delta arrives before the provider finishes; fragmented tool
  calls execute exactly once only after complete validation; abort closes the provider
  stream and prevents later tool execution/final completion; provider/orchestrator
  contract tests cover text-only, tool-only, mixed, malformed, error, and cancel paths.
- Detailed design and acceptance matrix: [03](./03-orchestration.md) §4a.

### B3.5 — bounded conversation context — **done**
- Persist an owned summary of older conversation prefixes while preserving every original
  message for history/audit.
- Keep the latest 8–12 messages verbatim; refresh after an estimated token threshold.
- Chunk large refreshes, validate terminal message markers/source counts, and reconstruct
  from originals when stale.
- Inject summaries as clearly delimited untrusted historical data.

### B3 exit criteria — **met (2026-07-29)**
- Loop is bounded, cancellable, traced (`run_id`).
- Read-only + low-risk tools live; one **form** HITL tool proven end-to-end (backend).
- Tool-using turns emit real provider text deltas; no sleep-based response simulation.
- Postgres telemetry is authoritative; Langfuse remains optional and deferred.

## 3. B4 — frontend chat for tools — **done**
- Render `step` / `tool_result` as compact cards; assistant prose stays bubble-less.
- **Form HITL card** (fields + OK/Cancel) wired to `confirmation_request` +
  `POST /api/chat/{id}/confirm` (composer blocked while pending).
- Scrape success already invalidates Scraper/library queries (client side-effect —
  **not** the LLM's job to "refresh" the page).
- **UI route context** + navigate chips (ADR-14): scrape → Open Scraper; play/resume
  auto-navigates and starts TTS, including on the current chapter (chip remains).
- `create_audio_download` adds confirmed chapter ranges with provider, live voice selection,
  and rate. SAPI/Zira defaults to 1.35×. After approval, the form disappears and an
  authoritative job card polls progress, auto-downloads on completion, and keeps a
  retry button. Download filenames include title + chapter range + short unique suffix.
- `update_ui_settings` applies theme/font/playback/voice/highlighting through a second,
  strict frontend allowlist.
- **Choice chips:** `propose_choices` tool → `choice_request` SSE → tap sends a
  normal user message (not a HITL gate).
- Cancellation leaves a compact note; streaming/status animation and post-render
  auto-scroll are wired; dark-mode controls use theme tokens.
- Cost meter visibility remains optional **[Q4]**, not a B4 blocker.
- **Accept (HITL path):** scrape confirm card renders, OK/Cancel resumes SSE; lint/tsc/build/tests green.
- **Accept (context path):** chat request includes route context; scrape success can
  offer navigate-to-Scraper without asking the model to refresh React Query; reader
  tools auto-navigate when off `/read/...`.

## 4. Milestone C — north-star assistant

Current status and remaining order:

1. **Title/alias discovery — done:** all four supported sources are searched and
   candidates retain ranked source metadata.
2. **Clarify / multi-match — done:** `propose_choices` drives normal follow-up turns.
3. **Ranked source → import/scrape HITL — done:** no pasted URL required.
4. **Persisted owned-book summaries — done:** content hash invalidation + cached tools.
5. **EPUB import — done:** preview plus bounded chunked import with UI progress.
6. **Theme/trope discovery — next:** support recommendation-style requests rather than
   repeatedly retrying title search; prevent raw external-budget failures.
7. **Summarize candidate before import:** spoiler-light metadata/source overview.
8. **Discuss owned books:** richer grounded multi-step answers over last-read chapters
   and library Q&A
   (prefer cached summary, then chapter FTS / `get_chapter_content`).
9. **More gated tools:** full-book download, delete/overwrite, retry large jobs.
10. **Eval harness** ([05](./05-observability.md) §6).
11. **RAG / embeddings only if measured quality still needs it** (`EMBEDDING`, pgvector).

**C accept (title→scrape path):** user can say a book title (optional start chapter),
confirm a suggested match, and get a scrape job without pasting a site URL; if two
sites list the book, the system picks or proposes the richer source.

### 4a. Persisted book summaries **[R][D → ADR-13]** — **done**

**Problem:** Re-summarizing from chapters on every “what’s this about?” is slow and
burns free-tier quota. Title-only search is too weak; chapter FTS is right for needles
but heavy for repeated overview questions.

**Implemented:**

1. Added the `book_summaries` table with:
   - `book_id`, ownership/`user_id` as needed
   - `kind` (`no_spoiler` / `blurb` / `chapter_range` / `full`)
   - `content` + optional structured JSON (themes, setting, tropes)
   - `source` (`llm` / `metadata` / `import`)
   - `model`, `prompt_version`, `content_hash` (invalidate when chapters change)
   - timestamps
2. Added `get_book_summary` (read cache) and `summarize_book`
   (provider-agnostic structured generation when missing/stale).
3. Search uses **summary/metadata first → chapter FTS fallback**
   (`search_library_content`).
4. Generates **on demand** — does not bulk-summarize the
   whole library on free tier by default.
5. Treats summary text as **untrusted data** in prompts (same as book/tool text).

**Accept:** second “summarize this book” call returns the cached row without a new
provider call when `content_hash` is unchanged; after chapter upsert/scrape, hash
mismatch forces refresh.
## 5. Cross-cutting, do-once-then-reuse

- **Prompt architecture:** authoritative system prompt; untrusted content clearly
  delimited as data; tool schemas as the only action surface; instruct clarify-vs-HITL
  behavior. Lock this in B3.0 and reuse.
- **Rate limiting:** per-user/per-tool/per-source — primitive in B3.0, apply per tool.
- **Central fetcher / SSRF guard:** required before any `touches_external` tool (B3.3 / C).

## 6. Dependencies at a glance

| Slice | Requires |
|-------|----------|
| B3.0 | B2 chat/SSE, B1 provider (`TOOL_CALLING`) |
| B3.1–B3.2 | B3.0 engine + domain services |
| B3.3 | central fetcher/SSRF, form HITL transport |
| B3.4 | B1 provider abstraction + B3 loop/SSE + Gemini streaming tool API |
| B3.5 | B1 structured output + owned conversation/message persistence |
| B4 | B3 SSE event types (`confirmation_request.form`, optional `choice_request`) |
| C (discovery) | `discovery` module, external-source review [Q12], B3.3 form HITL |
| C (summaries) | `book_summaries` table + summarize tools; chapter FTS already available |

## 7. Definition of done reminder (rule 85)

Every slice: backend `ruff`/`mypy`/`pytest -m "unit or integration"` green; frontend
`lint`/`format`/`build`(tsc)/`test` green. Frontend size limits (max-lines 110,
max-lines-per-function 60, max-depth 3) apply — keep splitting hooks/components as we did
for the chat UI.
