# RTM v3 — LLM Planning

> **Purpose:** One place that holds the planning, decisions, and detailed designs
> for the RTM conversational assistant across all phases (Milestone B and C).
>
> **Audience:** The maintainer and external reviewers. If you are reviewing, start
> with this page, then read the topic docs in order.

This directory is the umbrella for LLM/assistant planning. It builds on two
existing documents and does not replace them:

- [phase-0-discovery.md](../phase-0-discovery.md) — locks the overall product,
  stack, module boundaries, and milestones.
- [milestone-b-llm-spec.md](../milestone-b-llm-spec.md) — the B1 foundation spec
  (provider abstraction, model router, telemetry tables) that already shipped.
- [assistant-capabilities.md](../assistant-capabilities.md) — **what works now**
  (Hebrew capabilities sheet + example prompts).

## Legend

| Tag | Meaning |
|-----|---------|
| **[U]** | User / phase-0 locked requirement |
| **[R]** | Recommendation locked in these docs |
| **[D]** | Decision (ADR) — see [07-decision-log.md](./07-decision-log.md) |
| **[Q]** | Open question for review |

## Current status (2026-07-28)

| Slice | Scope | Status |
|-------|-------|--------|
| **B1 — Foundation** | `modules/llm`, Gemini adapter, capability router, telemetry tables, `GET /api/llm/models` | Done |
| **B2 — Chat + SSE** | `POST /api/chat` streaming, conversation persistence, assistant panel wired to real (tool-less) replies | Done |
| **B2.5 — Chat UX polish** | Markdown rendering (streamdown), no-bubble assistant turns, auto-scroll, themed scrollbar, smooth expand/shrink, "New chat" | Done |
| **B3 — Tools + orchestrator** | Tool registry, hand-rolled loop, budgets, read-only + low-risk tools, form HITL | **In progress (B3.3 form HITL done; B3 exit = Langfuse profile optional)** |
| **B4 — Frontend chat (tools)** | Tool-step affordances, form confirmation cards, clarify choices, **UI route context + navigate chips**, cost/status UI | **In progress (HITL form card; scrape list invalidate)** |
| **C — Full assistant** | Discovery search, **persisted book summaries**, gated scrape/import, richer Q&A / discuss | Planned |

## How to read these docs

Read in this order:

1. [00-north-star.md](./00-north-star.md) — product intent and the canonical
   discovery → summarize → form-HITL scrape session.
2. [01-architecture.md](./01-architecture.md) — the target request/response flow
   and where the new `tools` + `orchestration` modules sit.
3. [02-tools.md](./02-tools.md) — the tool contract, the full tool catalog, and
   the order we build them.
4. [03-orchestration.md](./03-orchestration.md) — the hand-rolled loop, budgets,
   the SSE event protocol, and the LangGraph decision.
5. [04-hitl.md](./04-hitl.md) — form HITL + clarify/choices (not only Approve/Decline).
6. [05-observability.md](./05-observability.md) — telemetry as source of truth and
   the Langfuse decision.
7. [06-roadmap-and-sequencing.md](./06-roadmap-and-sequencing.md) — the concrete
   build order with acceptance criteria per slice.
8. [07-decision-log.md](./07-decision-log.md) — every ADR in one place.

## Golden rules that constrain all of this (from phase-0 + rules)

1. **The LLM only acts through tools.** It never touches the DB, filesystem,
   internal services, arbitrary URLs, or shell.
2. **The backend is authoritative.** Tools validate args, re-check authz/ownership
   independent of the model, execute, and audit.
3. **Provider-agnostic.** Domain/business code never imports an LLM SDK; it depends
   on `LLMProvider` and requests capabilities, not model names.
4. **Untrusted content stays data.** Scraped/book/tool text can never redefine
   instructions, select tools, or expose secrets.
5. **No uncontrolled agent loops.** Every run is bounded by iteration, token, cost,
   and wall-clock caps, is cancellable, and carries a trace id.

## Locked recently (maintainer)

- **Hand-rolled loop for B3** (not LangGraph) — spine grows toward the north star;
  revisit triggers unchanged ([03](./03-orchestration.md), ADR-3).
- **HITL = forms + clarify/choices**, not only Approve/Decline ([04](./04-hitl.md),
  ADR-8/12).
- **Persist LLM book summaries** in a dedicated table (cache + search surface; invalidate
  on chapter changes) — required for Milestone C ([06](./06-roadmap-and-sequencing.md),
  ADR-13).
- **Title → match → smart source → scrape** (no pasted URL) is a first-class north-star
  path ([00](./00-north-star.md) §2b): discovery by title, clarify if ambiguous, rank
  sources (prefer more chapters), resolve book/start URLs, then form HITL scrape.
- **UI route context + client navigate** (ADR-14): chat turns get current path /
  reader ids as data; list refresh is FE invalidation; go-to-Scraper / reader open are
  client actions — not LLM-driven SPA control ([01](./01-architecture.md) §7,
  [06](./06-roadmap-and-sequencing.md) §3).

## Open questions for the reviewer

- **[Q1]** Tool batching order in [06](./06-roadmap-and-sequencing.md): ship all
  read-only tools before any action tool, or vertically slice (one read + one action
  end-to-end) to exercise the loop sooner?
- **[Q2]** Enable Langfuse at B3 start (better multi-step debugging) or defer until a
  concrete need — see [05](./05-observability.md)?
- **[Q4]** Do we want per-conversation budgets to be user-visible (cost meter) in B4,
  or internal-only until C?
- **[Q5]** How early to schedule discovery search relative to B3 library tools — see
  [00](./00-north-star.md) §5 and [06](./06-roadmap-and-sequencing.md)?
