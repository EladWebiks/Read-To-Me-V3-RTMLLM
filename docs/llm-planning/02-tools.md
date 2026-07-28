# 02 — Tools: contract, catalog & build order

> Tools are the **only** way the assistant acts. The model picks a tool; the backend
> validates, authorizes, executes, and audits. See rules `45-tools-orchestration`,
> `40-llm-provider`, `60-security`, and the `add-llm-tool` skill.

## 1. The tool contract **[U]**

Every tool declares:

| Field | Purpose |
|-------|---------|
| `name`, `description` | Identity; description is shown to the LLM, so it must be crisp |
| `input_schema` (pydantic) | Doubles as the LLM function schema; validated before execute |
| `output_schema` (pydantic) | Backend-authoritative result shape; validated before return |
| `risk_level` | `read_only` \| `low_risk` \| `confirmation_required` |
| `read_only` | Pure read, no state change |
| `touches_external` | Makes outbound network calls (scraping/discovery) |
| `allowed_in_internal_only` | May run when external calls are disabled |
| `rate_limit`, `timeout_ms` | Per-user / per-tool caps |
| `idempotency_key` (optional) | For retry-safe actions (e.g. create download) |
| `authorize(ctx)` | Ownership + permission check, **independent of the model** |
| `execute(input, ctx)` | Calls one domain service using `ctx.user_id` |

### Execution contract (orchestrator enforces, in order) **[U]**

1. Validate args against `input_schema`.
2. Check **authz + ownership** (independent of the LLM's claims).
3. Check risk / confirmation and current mode (`internal_only` blocks external tools).
4. Apply rate limit / idempotency.
5. Execute with timeout → validate output → audit to `tool_call` → return structured result.

### Hard rules

- A tool **wraps a domain service**; it holds no business logic. If the capability
  doesn't exist, add it to the owning module first.
- `confirmation_required` tools **pause for approval** (HITL) before executing — never
  auto-run destructive/expensive/external actions.
- A tool never returns secrets or another user's data.
- Tool text/results are **data**, not instructions.

## 2. Tool definition shape (proposed)

```python
class ToolResult(BaseModel):
    ok: bool
    data: BaseModel | None = None
    error: str | None = None

class Tool(Protocol[TInput, TOutput]):
    name: str
    description: str
    input_schema: type[TInput]
    output_schema: type[TOutput]
    risk_level: RiskLevel
    read_only: bool
    touches_external: bool
    allowed_in_internal_only: bool
    rate_limit: RateLimit
    timeout_ms: int
    idempotency_key: str | None

    async def authorize(self, inp: TInput, ctx: ToolContext) -> None: ...  # raises if denied
    async def execute(self, inp: TInput, ctx: ToolContext) -> TOutput: ...
```

The **registry** (`tools/registry.py`) exposes:
`list_specs(mode)` → the tool JSON schemas the orchestrator sends to the LLM
(filtered by mode), and `resolve(name)` → the tool instance.

## 3. Tool catalog

Grounded in phase-0 §14 and the domain services that already exist
(`library`, `books`, `chapters`, `reader`, `audio`, `downloads`, `scraping`).

### Read-only (no confirmation) — **Batch 1**

| Tool | Wraps | Notes |
|------|-------|-------|
| `search_user_books` | `library.service` | Filter/search the user's library |
| `get_book_details` | `books.service` | Metadata for one owned book |
| `get_reading_progress` | `reader.service` | Progress for a book |
| `get_recently_read_chapters` | `reader.service` | Recent activity |
| `list_available_chapters` | `chapters.service` | Chapter index for a book |
| `get_chapter_content` | `chapters.service` | One chapter's text (owned) |
| `search_library_content` | `library`/FTS | Full-text search across owned content |
| `get_download_status` | `downloads.service` | Status of a user's download job |

All are `read_only=true`, `touches_external=false`, `allowed_in_internal_only=true`.

### Low-risk actions (state change, no confirmation) — **Batch 2**

| Tool | Wraps | Why low-risk |
|------|-------|--------------|
| `play_chapter` | `audio.service` | Starts TTS playback; reversible, cheap |
| `resume_book` | `reader.service` | Updates "current" pointer; reversible |
| `create_chapter_download` | `downloads.service` | **Single** chapter job; `idempotency_key` |

`create_chapter_download` for a **single** chapter is low-risk; a **range/full book**
download is `confirmation_required` (see below).

### Confirmation-required (HITL) — **Batch 3 / Milestone C**

| Tool | Wraps | Why gated |
|------|-------|-----------|
| `scrape_book_range` | `scraping.service` | External + expensive + large range |
| `scrape_full_book` | `scraping.service` | External + expensive |
| `create_book_download` (range/full) | `downloads.service` | Large archive |
| `retry_failed_job` (large) | `scraping`/`downloads` | Re-spends quota |
| `delete_book` / `overwrite_chapters` | `library`/`chapters` | Destructive |
| `import_discovered_book` | `discovery` (C) | External import |

All `confirmation_required` tools with `touches_external=true` set
`allowed_in_internal_only=false`.

## 4. Build order for tools

**[R]** Ship the loop with the smallest safe tool set, then widen:

1. **B3.0** — orchestration skeleton + registry + `ToolContext` + audit, plus
   **2 read-only tools** (`search_user_books`, `get_book_details`) to exercise the loop.
2. **B3.1** — the rest of **Batch 1** (read-only).
3. **B3.2** — **Batch 2** (low-risk actions).
4. **B3.3** — HITL gate + first **Batch 3** tool (`scrape_book_range`).
5. **C** — remaining confirmation-required + discovery tools.

**[Q1]** Alternative: a thin vertical slice (one read + `play_chapter`) first to prove
the end-to-end action path earlier. Reviewer to weigh in.

## 5. Security checklist per tool (from `60-security` + skill)

- [ ] `authorize(ctx)` enforces ownership using `ctx.user_id` (not `input`).
- [ ] External tools go through the central fetcher (SSRF allowlist) and are blocked
      in `internal_only`.
- [ ] Rate limit per-user/per-tool set; `timeout_ms` set.
- [ ] Output schema returns no secrets / no other user's rows.
- [ ] `confirmation_required` cannot execute without a recorded confirmation.
- [ ] Every execution writes a `tool_call` audit row.

## 6. Required tests per tool (from skill)

- Happy path.
- AuthZ failure / another user's data → denied.
- Invalid input rejected by schema.
- `confirmation_required` does not execute without confirmation.
- External tool blocked in `internal_only`.
- Prompt-injection: a tool result containing "ignore previous instructions" changes
  nothing (it is data).

## 7. `tool_call` audit row (already in the data model)

`tool_call(id, message_id, tool_name, input jsonb, output jsonb, status, duration_ms,
risk_level, confirmed_by_user, error, created_at)` — written on **every** execution,
success or failure. This is the source for tool success-rate and confirmation-rate
metrics ([05](./05-observability.md)).
