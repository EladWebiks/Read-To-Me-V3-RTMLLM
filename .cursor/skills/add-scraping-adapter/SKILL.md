---
name: add-scraping-adapter
description: Add a new deterministic per-site scraping adapter to RTM v3 with saved-HTML fixtures and a contract test. Use when adding support for scraping a new book/novel website, or porting a v2 adapter (novelbin, novelfull, freewebnovel, novellunar).
---

# Add a scraping adapter

Deterministic adapters are the preferred parser for known sites; the LLM is only a fallback. See rules `50-scraping`, `60-security`.

## Steps

1. **Register the source** first: add a `scraping_source` (name, base domains, enabled=false until ready, rate_limit, robots/ToS note). Only enabled + allowlisted domains may be fetched.
2. **Create the adapter** in `modules/scraping/adapters/<site>.py` implementing the common interface:
   `supports_url`, `parse_book_page`, `extract_book_metadata`, `find_first_chapter`,
   `parse_chapter`, `find_next_chapter`, `find_previous_chapter`, `estimate_chapter_count`,
   `validate_chapter_sequence`.
   - Return typed models (`BookMetadata`, `ChapterData`) — mirror v2's shape (title, content, next_url, chapter_number, book_title, book_author).
   - Use the **central fetch service** (never call `httpx`/`cloudscraper`/Playwright directly) so SSRF guard, rate limit, timeout, and size caps apply.
   - Detect placeholder/empty chapters to stop cleanly.
3. **Register** the adapter so it resolves by `supports_url` (first match wins).
4. **Save fixtures:** capture real HTML for a book page + a few chapter pages into `backend/tests/fixtures/scraping/<site>/`. These are the regression source of truth.
5. **Contract test** (`tests/scraping/test_<site>.py`): run each interface method against the fixtures and assert extracted metadata, content cleaning, next/prev navigation, and chapter numbering. No network in tests.
6. **Cleaning:** apply the shared cleaning-rules pipeline; add site-specific rules only if needed.
7. **Enable** the source once tests pass; verify robots.txt/ToS and per-site rate limit are respected.

## Checklist
- [ ] Source registered + domain allowlisted, initially disabled
- [ ] All interface methods implemented, fetching via central fetch service
- [ ] Fixtures saved; contract test passes offline
- [ ] Placeholder/last-chapter detection works
- [ ] Rate limit + robots/ToS honored; source enabled last
- [ ] Scraped content treated as untrusted (sanitized, never instructions)
