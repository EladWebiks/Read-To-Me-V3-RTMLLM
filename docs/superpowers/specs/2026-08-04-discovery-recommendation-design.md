# Discovery recommendation (T1) — Design

Date: 2026-08-04
Status: Approved (plan)

## Goal

Support “find N books like X / theme” prompts with **one** external assistant
tool call instead of one `search_discovered_books` call per guessed title,
without raising `LLM_MAX_EXTERNAL_CALLS`.

## Source strategy

| Candidate | Finding | Decision |
|-----------|---------|----------|
| **NovelUpdates** | No public API; Cloudflare; staff historically discourage scraping; community scrapers are brittle | **Reject** as a primary RTM source (conflicts with deterministic fetcher + ToS posture) |
| **WLNUpdates** | Documented JSON `/api` with series/tags/genres | **Defer** (T1.1) — promising allowlisted theme→title index later |
| **Existing 4 scrape sources** | novelfull, novelbin, freewebnovel, novellunar — already registered, SSRF-allowlisted, aligned with scrape adapters | **Primary path for T1** |
| **Free-form web search** | Burns budget; hard to authz/SSRF | **Out of T1** |

Product shape (“tag/theme → titles → scrapable URLs”) remains valid.
NovelUpdates is the wrong concrete site for that shape.

## Problem today

`search_discovered_books` accepts **one title per tool call**. A prompt like
“Find three books like Against the Gods” makes the model guess titles and
invoke the tool repeatedly until it hits `LLM_MAX_EXTERNAL_CALLS=3`. Raising
that cap hides inefficient tool use rather than fixing discovery.

## Locked approach

1. **`DiscoveryService.recommend(...)`** — domain-owned batch:
   - Inputs: optional owned `seed_book_id`, `themes`, `candidate_titles` (≤10),
     `limit` (default 3, max 10), `exclude_owned` (default true).
   - Query set: candidate titles first; if a seed is present and candidates are
     empty/short, derive extra queries from owned title/author (and cached
     summary keywords when available). No open web search.
   - Themes alone never invent titles. No candidates and no seed → clear
     validation error (model must pass candidates and/or seed in the same call).
   - Fan-out `search_all_sources` per query with small concurrency (2), existing
     SSRF/timeouts, hard cap of 8 queries, early stop when enough distinct books.
   - Upsert via existing hit path; dedupe by `normalized_title`; exclude owned;
     rank (title match + source richness + chapter estimate + theme token overlap);
     return evidence (which query / theme matched).

2. **Tool `recommend_discovered_books`** — `READ_ONLY`, `touches_external=True`,
   timeout ~60s. Counts as **one** orchestrator external-budget unit for the
   whole batch. Keep default `LLM_MAX_EXTERNAL_CALLS=3`.

3. Keep **`search_discovered_books`** for exact title lookup. Import still goes
   through **`import_discovered_book`** + **`propose_choices`** (no new scrape path).

4. Prompt/tool copy steers “books like X / theme” to `recommend_discovered_books`.

## Out of scope (this ship)

- Scraping NovelUpdates / Cloudflare browser automation
- New discovery SPA page
- Candidate-before-import summaries
- Embeddings / pgvector theme search
- Raising `LLM_MAX_EXTERNAL_CALLS` as the “fix”
- WLNUpdates integration (**T1.1** — see
  [`2026-08-04-discovery-theme-index-design.md`](2026-08-04-discovery-theme-index-design.md))

## Acceptance

- Design doc checked in with source decision rationale.
- “Find 3 books like X” can complete with one `recommend_discovered_books` call.
- Results are real upserted discovery rows with scrapable sources; import HITL unchanged.
- Owned books excluded when requested; evidence returned per candidate.
- Quality gates green.
