---
name: add-llm-tool
description: Add a new tool the RTM v3 LLM assistant can call, with pydantic input/output schemas, risk level, authorization, audit, and tests. Use when exposing a backend capability to the conversational assistant (e.g. play_chapter, create_chapter_download, search_user_books).
---

# Add an LLM tool

Tools are the ONLY way the assistant acts. The backend validates and executes; the model just picks the tool. See rules `45-tools-orchestration`, `40-llm-provider`, `60-security`.

## Steps

1. **Wrap an existing domain service.** A tool must not contain business logic — it calls a service method. If the capability doesn't exist yet, add it to the owning module first.
2. **Define schemas** (pydantic) in the tool file: `InputModel` and `OutputModel`. These double as the LLM function schema, so field names/descriptions must be clear and self-documenting.
3. **Classify the tool:**
   - `risk_level`: `read_only` | `low_risk` | `confirmation_required`
   - flags: `read_only`, `touches_external`, `allowed_in_internal_only`
   - `rate_limit`, `timeout_ms`, optional `idempotency_key`
   - Destructive / expensive / external / large-range / import → `confirmation_required` (HITL).
4. **Implement** `authorize(ctx)` (ownership + permission checks, independent of the model) and `execute(input, ctx)` (calls the service using `ctx.user_id`).
5. **Register** the tool in the tool registry so the orchestrator can expose it.
6. **Audit:** ensure execution writes a `tool_call` record (input, output, status, duration, risk, confirmed_by_user).
7. **Tests (required):**
   - happy path
   - authz failure / accessing another user's data → denied
   - invalid input rejected by schema
   - `confirmation_required` tool does not execute without confirmation
   - (if external) blocked in `internal_only` mode

## Checklist
- [ ] Input + output pydantic schemas with descriptions
- [ ] risk_level + flags + rate limit + timeout set correctly
- [ ] authorize() enforces ownership independently of the LLM
- [ ] execute() only calls a domain service; returns no secrets/other users' data
- [ ] registered + audited
- [ ] tests incl. authz + injection/confirmation cases pass

## Reference tool names (from phase-0 §14)
`search_user_books`, `get_book_details`, `get_reading_progress`, `get_recently_read_chapters`, `get_chapter_content`, `play_chapter`, `resume_book`, `list_available_chapters`, `create_chapter_download`, `get_download_status`, `search_library_content`.
