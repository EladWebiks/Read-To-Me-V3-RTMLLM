# 00 — North star: what the assistant is for

> Locked product intent for the conversational assistant. Architecture and sequencing
> must grow toward this story. Hand-rolled orchestration stays (ADR-3); HITL is
> **forms + clarify/choices**, not only Approve/Decline — see [04-hitl.md](./04-hitl.md).

## 1. Super-goal **[R]**

The assistant is a **full conversational front-end to the product**, plus abilities
the GUI does not emphasize (discovery search, spoiler-light summaries, multi-step
import with parameters).

It should be able to:

- Do **everything the website can do** via tools (library, reader, play, download,
  scrape, remove, progress, …).
- Do **more**: search for books the user does not have yet, summarize candidates,
  enqueue scrapes with user-chosen parameters, reason about job queues, discuss
  owned content grounded in chapters.

It never acts by itself on expensive/destructive/external work — it **asks** when
intent is unclear, when there are multiple choices, or when confirmation + params
are required.

**Current delivery:** title discovery across four sources, ranked import/scrape HITL,
owned-book summary caching, play/resume, configurable range downloads, and reversible
settings are shipped. Theme/trope discovery, candidate-before-import summaries, and
richer grounded discussion remain.

## 2. Canonical session (target UX)

Illustrative happy paths. Exact tool names may differ; the *shape* is what we build toward.

### 2a. Theme / discovery → summarize → form-HITL scrape

1. **User:** “Find me books about cultivation in modern time.”
2. **Assistant:** Searches (discovery / sources), filters out books already in the
   library, lists candidates (e.g. book1…book5), asks which to pursue.
3. **User:** “Book 2 sounds interesting — summarize it.”
4. **Assistant:** Spoiler-light summary (metadata / blurb / controlled fetch — not a
   full scrape). Offers to add to library.
5. **User:** “Yes, add it.”
6. **Assistant → HITL form:** scrape parameters (optional start chapter; chapter count
   or empty = entire book). User fills / accepts defaults → OK.
7. **System:** Enqueues scrape job; user can see progress on the scraper page.
8. **Assistant:** “Added to your library; scrape is in progress. Anything else?”
9. **User:** “Add book 3 too.”
10. **Assistant → HITL form again** → OK → job queued behind the first.

### 2b. Title → match → smart source → scrape (no URL from the user) **[R]**

This is a first-class north-star path (same product as 2a; different entry):

1. **User:** “Scrape *Shadow Slave*” / “Add the book called X starting at chapter 50.”
2. **Assistant:** Discovery search by title (and aliases) across supported novel sites;
   excludes books already owned when relevant.
3. **If several matches:** clarify / choice (“Did you mean A, B, or C?”) — not a silent guess.
4. **User:** “Yes, that one” (or picks a chip).
5. **Assistant:** Resolves **book page URL** and **start chapter URL** from the chosen
   `book_source` (adapters already expose book page / first chapter; start chapter from
   user request or default 1). User does **not** paste URLs.
6. **Source choice:** if the same work exists on multiple sites, pick (or propose) the
   better source — prefer **more available chapters** / fresher listing, with a short
   reason; user can override in clarify or the HITL form if we expose source.
7. **HITL form:** start chapter + chapter count (empty = entire) → OK → enqueue scrape
   (same gate as today’s `scrape_book_range`, eventually via `import_discovered_book`).

**Not acceptable as the long-term UX:** requiring the user to find and paste a site URL
before scrape. URL-based scrape (B3.3) is a spine/bootstrap path only.

Other first-class actions in the same product: remove a book/chapter, download
chapters, play from where I left off, “what happened in the last few chapters of my
last-read book,” etc.

Confirmed audio downloads use the same pattern: editable range/provider/voice/rate,
then an authoritative progress card and automatic named MP3 download. Approval itself
is not rendered as a durable outcome.

## 3. Capability map (example → building blocks)

| Moment in the story | Building block |
|---------------------|----------------|
| Genre / theme search, exclude owned | Discovery tools + library membership filter |
| **Title search → “did you mean?” → scrape** | Discovery + clarify + source rank + import/scrape HITL (§2b) |
| Multi-site same book | Rank `book_source`s (prefer more chapters / fresher); user can override |
| Resolve book page + start chapter without pasted URL | Adapter metadata on `book_source` (`book_page_url`, `first_chapter_url`, …) |
| Summarize a candidate before import | Summary tool / capability (not full scrape); **persist** when useful |
| Repeated “what’s this book about?” on owned books | **`book_summaries` cache** + chapter FTS fallback ([06](./06-roadmap-and-sequencing.md) §4a) |
| “Add to library” with chapter range | `confirmation_required` + **HITL form** |
| Progress visible on scraper page | Existing scrape jobs; tool only enqueues |
| Second book while first runs | Queue-aware scrape/download tools |
| Play / download / remove / discuss owned | Domain tools (Batches 1–3 in [02](./02-tools.md)) |
| Unclear intent or several matches | **Clarify / choice** UX (not a tool execute) |

## 4. What this does *not* require

- **LangGraph** — the story needs tools, form-HITL, discovery, and a pausable loop.
  Framework optional later (ADR-3 revisit triggers still apply).
- Autonomous browsing or unconstrained agent loops.
- The model touching DB / jobs / network directly.

## 5. Implications for sequencing

- B3 builds the **spine** (loop, registry, budgets, audit) that this story hangs on.
- HITL is designed from day one as **structured forms + clarify/choices**, even if
  the first gated tool ships with a small form.
- Discovery / “books I don’t own yet” is **core to the north star**, not a nice-to-have
  afterthought — schedule it as soon as the spine and basic library tools work
  (see [06](./06-roadmap-and-sequencing.md)).
- **Persisted book summaries** are required work (not optional polish): generate on
  demand (or after scrape), store with provenance + content-hash invalidation, search
  summaries first and fall back to chapter FTS.