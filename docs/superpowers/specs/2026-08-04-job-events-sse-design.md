# Job-events SSE (T5) — Design

Date: 2026-08-04
Status: Approved (plan)

## Goal

Replace hot job polling (scrape, download, EPUB import) with a shared
per-user SSE stream. React-query stays the source of truth; SSE only
invalidates / lightly patches caches. Admin Jobs, Google SSO popup poll,
and cosmetic UI timers stay as they are.

## Decisions

1. **Transport:** SSE (same family as chat), not WebSockets.
2. **Shape:** one multiplex stream per user — `GET /api/jobs/events` —
   not one connection per job.
3. **Bridge:** after each durable job progress write, publish a typed
   event on Redis channel `rtm:user:{user_id}:jobs`.
4. **Hybrid catch-up:** on connect / reconnect the client does REST
   refetches; Redis is not a durable queue.
5. **Fallback:** if the SSE stream is down, hooks keep their previous
   conditional `refetchInterval` / poll behavior.

## Event contract

```json
{
  "v": 1,
  "kind": "scrape|download|import",
  "job_id": "<uuid>",
  "user_id": "<uuid>",
  "status": "<string>",
  "progress": { "done": 3, "total": 10 },
  "book_id": "<uuid|null>",
  "updated_at": "<iso8601>"
}
```

- Emit on status transitions and meaningful progress ticks
  (e.g. scrape `chapters_done`).
- Always emit terminal statuses (`complete` / `failed` / `cancelled`
  and import equivalents).
- No chapter bodies, file bytes, or secrets in the payload.

## Backend

- Shared helper in `app/core/job_events.py` (+ thin router module
  `modules/job_events/` for `GET /api/jobs/events`).
- Session auth via `get_current_user`; channel key is server-derived
  from `user.id` (never client-supplied).
- Heartbeat SSE comment every ~15s.
- Initial `ready` event so the client can start catch-up refetches.
- Publishers: scraping worker, downloads worker, imports job progress
  — after successful DB flush/commit.

## Frontend

- `useJobEvents` (shared hook): credentials-included stream, reconnect
  with backoff, visibility-aware pause/resume.
- On `scrape`: invalidate scrape job list/detail + library books.
- On `download`: invalidate download detail + book list when `book_id`
  present.
- On `import`: drive EPUB import UI + invalidate library on completed.
- Disable aggressive polling while stream is healthy.

## Out of scope

- Admin cross-user live Jobs monitor.
- Chat / HITL SSE protocol changes.
- Runtime-config / LLM catalog Redis invalidation.
- WebSockets / third-party realtime vendors.
