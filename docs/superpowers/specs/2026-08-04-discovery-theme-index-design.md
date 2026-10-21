# Discovery theme→title index (T1.1) — Design

Date: 2026-08-04
Status: Approved (plan)

## Goal

Let `recommend_discovered_books` accept **themes alone** and expand them to
candidate titles via an allowlisted index, then continue with the existing
four-source scrape fan-out from T1.

## Source decision

| Candidate | Finding | Decision |
|-----------|---------|----------|
| **NovelUpdates** | No public API; staff discourage scraping; Cloudflare | **Reject** |
| **WLNUpdates** | Documented JSON `POST /api`; enumerate tags/genres; `search-advanced` | **Primary** |
| **DaoSearch** | Public REST; CN/Qidian-heavy | **Defer** (possible T1.2) |

WLN is an **index only** — never a chapter scrape adapter.

## Flow

1. Themes (and optional seed/candidates) enter `DiscoveryService.recommend`.
2. If the query pool is empty/short and themes are present, call WLN once:
   map themes → tag/genre names → `search-advanced` → titles (capped).
3. Fan out those titles across the four scrape sources (unchanged T1 path).
4. Evidence notes `wlnupdates theme '…'` when titles came from the index.

## Caps / safety

- Central fetcher only (`post_json`); host allowlist `wlnupdates.com` /
  `www.wlnupdates.com` separate from scrape chapter hosts.
- ≤1 WLN advanced search per recommend; ≤10 titles into the query pool;
  ≤3 matched tags/genres per call.
- Soft-fail if WLN is down when other queries exist; hard validation error
  only when no usable queries remain.

## Out of scope

NovelUpdates, DaoSearch dual-index, discovery SPA, embeddings, raising
`LLM_MAX_EXTERNAL_CALLS`, scraping chapters from WLN.
