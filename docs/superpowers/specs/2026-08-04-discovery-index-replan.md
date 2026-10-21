# Discovery index replan (T1.2) — Design

Date: 2026-08-04
Status: Approved (implementing)

## Why replan

T1.1 assumed **WLNUpdates** (`POST /api`) as the theme→title index. Live
checks return **HTTP 500**. Theme expansion yields zero titles; the model then
falls back to `search_discovered_books("Against the Gods")` → lookalikes.

Hardcoded theme→title maps were rejected. NovelUpdates / WebNovel stay
unreachable behind Cloudflare with no public API. Novel-Index is FR HTML-only
and deferred. DaoSearch returns CN/Qidian Google-translated titles that rarely
match our EN scrape sites — **not used** in the recommend title pool.

Google Search grounding (`use_web_search=True`) was tried as primary index but
hits free-tier **429 RESOURCE_EXHAUSTED** while plain structured generation on
the same key still returns good EN web-novel titles. Grounding is deferred
until billing/quota supports it.

## Locked approach

**Primary index:** plain Gemini **structured output** via
`StructuredOutputRequest(use_web_search=False)` — domain-locked prompt asks for
well-known English fan-translation titles similar to themes/seed. No Google
Search grounding. No hardcoded title maps.

**Verify:** existing four scrape sources (novelfull, novelbin, freewebnovel,
novellunar). Keep only scrapable hits.

**Not in the pool:** DaoSearch, WLNUpdates, hardcoded maps, grounding (until
quota allows).

**Hard fail** when:
- title research LLM call fails (surface the real error, e.g. rate limit), or
- research returns no titles for themes/seed, or
- researched titles have zero scrapable sources.

Clear error; never seed lookalike search; never invent titles after a failed
tool call in the chat turn.

Optional `candidate_titles` (OTHER books) still scrape-verified when the
model supplies them.

## Caps / safety

- Discovery depends on `LlmService` + `STRUCTURED_EXTRACTION` without
  `use_web_search`.
- Prompt locks domain: English-translated web/light novels; “Against the Gods”
  = 逆天邪神, not Bernstein finance.
- ≤1 research call per recommend; ≤10 titles into scrape pool.
- Model-proposed titles are untrusted candidates until scrape-verified.

## Out of scope

NovelUpdates, WebNovel reverse-eng, Novel-Index HTML adapter, embeddings,
DaoSearch as recommend expander, Google Search grounding (revisit with paid
tier).

## Acceptance

- Themes / “books like seed” expand via structured LLM title research.
- No hardcoded theme→title map in the product path.
- Research failure / empty / unscrapeable → clear `DiscoveryRecommendError`.
- Quality gates green.
