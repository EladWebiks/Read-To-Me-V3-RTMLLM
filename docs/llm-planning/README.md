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

## Current status (2026-07-29)

| Slice | Scope | Status |
|-------|-------|--------|
| **B1 — Foundation** | `modules/llm`, Gemini adapter, capability router, telemetry tables, `GET /api/llm/models` | Done |
| **B2 — Chat + SSE** | `POST /api/chat` streaming, conversation persistence, assistant panel wired to real (tool-less) replies | Done |
| **B2.5 — Chat UX polish** | Markdown rendering (streamdown), no-bubble assistant turns, auto-scroll, themed scrollbar, smooth expand/shrink, "New chat" | Done |
| **B3 — Tools + orchestrator** | Tool registry, bounded hand-rolled loop, true streaming, tools, form HITL, rolling context | Done |
| **B4 — Frontend chat (tools)** | Tool progress, HITL forms, choices, route context, playback/download/settings client actions | Done (cost meter intentionally optional) |
| **C — Full assistant** | Discovery/import, persisted summaries, richer grounded discuss/Q&A | **In progress** (title + batched recommend discovery/import + summaries done; richer discuss next) |

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
- **True provider streaming for tool turns shipped in B3.4**: the provider contract
  streams Gemini text deltas directly, assembles partial tool calls in the adapter,
  preserves usage/cancellation, and has no artificial backend pacing
  ([03](./03-orchestration.md) §4a, [06](./06-roadmap-and-sequencing.md) §2).
- **Bounded conversation context shipped**: full messages remain stored for history/audit;
  older prefixes are summarized in owned rows once the threshold is crossed, while the
  latest 8–12 messages remain verbatim and summaries are injected as delimited untrusted data.
- **Useful client actions shipped**: play/resume starts TTS after navigation, confirmed audio
  range downloads expose provider/voice/rate, and reversible settings use a strict client
  allowlist.
- **Audio download completion shipped**: SAPI/Zira defaults to 1.35×; approved forms
  disappear; deterministic job cards poll progress, auto-download completed MP3s, and keep
  a retry button. Filenames include sanitized title + chapter range + short job suffix.
- **EPUB import shipped**: upload/preview/import uses bounded chunks and reports progress in
  the Scraper UI.
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

- **[Q2]** Enable Langfuse at B3 start (better multi-step debugging) or defer until a
  concrete need — see [05](./05-observability.md)?
- **[Q4]** Do we want per-conversation budgets to be user-visible (cost meter) in B4,
  or internal-only until C?
- **[Q5]** Discovery timing — partially resolved: title discovery/import pulled into B/C
  (Jul 2026); theme/trope search still open.
- **[Q6]** After theme discovery and richer grounded discussion, does measured quality
  justify adding embeddings/RAG?
