# 06 — Roadmap & sequencing

> The concrete build order from here, with acceptance criteria per slice. "What order
> to implement stuff." Aligns with [00-north-star.md](./00-north-star.md). Each slice
> must pass the quality gates in rule `85` before it is "done".

## 1. Big picture

```
B1 (done) ─► B2 (done) ─► B2.5 UX (done) ─► B3 tools+loop+form HITL ─► B4 tool UX ─► C north-star
```

- **B** = tool-using assistant with budgets + **form HITL** spine.
- **C** = discovery → summarize → import/scrape with forms; discuss owned books; RAG as needed.

Hand-rolled loop stays (ADR-3). We are not waiting on LangGraph to grow toward the
canonical session.

## 2. B3 — tools + orchestrator (next)

Delivered as small vertical slices so the loop is exercised end-to-end early.

### B3.0 — engine skeleton
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

### B3.1 — full read-only tool set (Batch 1)
- `get_reading_progress`, `get_recently_read_chapters`, `list_available_chapters`,
  `get_chapter_content`, `search_library_content`, `get_download_status`.
- **Accept:** authz matrix test per tool (own vs other user), schema-rejection test,
  injection test (tool text is inert).

### B3.2 — low-risk actions (Batch 2) — **done**
- `play_chapter`, `resume_book`, `create_chapter_download` (single, idempotent).
- `play_chapter` / `resume_book` update reading progress and return a client action
  payload (B4 wires the TTS player).
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

### B3 exit criteria
- Loop is bounded, cancellable, traced (`run_id`).
- Read-only + low-risk tools live; one **form** HITL tool proven end-to-end (backend).
- Langfuse compose profile available in dev (off by default) — see [05](./05-observability.md).

## 3. B4 — frontend chat for tools — **partial**
- Render `step` / `tool_result` as compact cards; assistant prose stays bubble-less.
- **Form HITL card** (fields + OK/Cancel) wired to `confirmation_request` +
  `POST /api/chat/{id}/confirm` (composer blocked while pending).
- Scrape success already invalidates Scraper/library queries (client side-effect —
  **not** the LLM's job to "refresh" the page).
- **UI route context** + navigate chips (ADR-14): scrape → Open Scraper; play/resume
  auto-navigates to the chapter when off-reader (chip remains).
- **Choice chips:** `propose_choices` tool → `choice_request` SSE → tap sends a
  normal user message (not a HITL gate).
- Still open: cost meter visibility **[Q4]**.
- **Accept (HITL path):** scrape confirm card renders, OK/Cancel resumes SSE; lint/tsc/build/tests green.
- **Accept (context path):** chat request includes route context; scrape success can
  offer navigate-to-Scraper without asking the model to refresh React Query; reader
  tools auto-navigate when off `/read/...`.

## 4. Milestone C — north-star assistant

Ordered by dependency and value (discovery is core, not optional fluff — **[Q5]** how
early relative to late B3):

1. **Discovery search** — theme *and* **title/alias** search across supported sites;
   exclude owned titles; return candidates with source URLs (no user-pasted URL required).
   See north star [00](./00-north-star.md) §2b.
2. **Clarify / multi-match** — “did you mean A/B/C?” when title is ambiguous.
3. **Smart source pick** — when the same work has multiple `book_source`s, rank (prefer
   **more chapters** / fresher listing); expose choice if close or user asks.
4. **Resolve book page + start chapter** from discovery metadata / adapters (first
   chapter or user-requested start) → feed scrape HITL without a pasted URL.
5. **Summarize candidate** before import (spoiler-light; no full scrape required).
6. **Persisted book summaries (required)** — see §4a below.
7. **Import + scrape with form HITL** (B3.3 gate; prefer `import_discovered_book` →
   scrape) + queue awareness when another job is running.
8. **More gated tools:** full-book download, delete/overwrite, retry large jobs.
9. **Discuss owned books:** grounded answers over last-read chapters, library Q&A
   (prefer cached summary, then chapter FTS / `get_chapter_content`).
10. **RAG / embeddings** if still needed for quality (`EMBEDDING`, pgvector).
11. **Eval harness** ([05](./05-observability.md) §6).

**C accept (title→scrape path):** user can say a book title (optional start chapter),
confirm a suggested match, and get a scrape job without pasting a site URL; if two
sites list the book, the system picks or proposes the richer source.

### 4a. Persisted book summaries **[R][D → ADR-13]** — must do

**Problem:** Re-summarizing from chapters on every “what’s this about?” is slow and
burns free-tier quota. Title-only search is too weak; chapter FTS is right for needles
but heavy for repeated overview questions.

**Work item (required in C, not optional polish):**

1. Add a `book_summaries` (or equivalent) table, e.g.:
   - `book_id`, ownership/`user_id` as needed
   - `kind` (`no_spoiler` / `blurb` / `chapter_range` / `full`)
   - `content` + optional structured JSON (themes, setting, tropes)
   - `source` (`llm` / `metadata` / `import`)
   - `model`, `prompt_version`, `content_hash` (invalidate when chapters change)
   - timestamps
2. Tools: `get_book_summary` (read cache) and `summarize_book` / `ensure_book_summary`
   (generate via `LONG_CONTEXT_SUMMARIZATION` + instructor if missing/stale).
3. Search path: **summary/metadata first → chapter FTS fallback**
   (`search_library_content`).
4. Generate **on demand** (or when a scrape job completes) — do not bulk-summarize the
   whole library on free tier by default.
5. Treat summary text as **untrusted data** in prompts (same as book/tool text).

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
| B4 | B3 SSE event types (`confirmation_request.form`, optional `choice_request`) |
| C (discovery) | `discovery` module, external-source review [Q12], B3.3 form HITL |
| C (summaries) | `book_summaries` table + summarize tools; chapter FTS already available |

## 7. Definition of done reminder (rule 85)

Every slice: backend `ruff`/`mypy`/`pytest -m "unit or integration"` green; frontend
`lint`/`format`/`build`(tsc)/`test` green. Frontend size limits (max-lines 110,
max-lines-per-function 60, max-depth 3) apply — keep splitting hooks/components as we did
for the chat UI.
