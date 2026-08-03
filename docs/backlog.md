# RTM backlog — post–admin-panel tickets

Working list of product/engineering tickets after `main` absorbed the admin
panel, runtime config, memberships, quotas, and usage UX.

Update status in this file as tickets move. One ticket at a time.

## Workflow (Model B — one backlog branch)

All tickets land on **`backlog-cleanup`**. One PR to `main` when the
batch is ready (or when we decide to cut a release).

1. **Discuss** the ticket in chat (goal, constraints, acceptance).
2. Stay on **`backlog-cleanup`** (create it from up-to-date `main` only if
   missing). Do **not** open a per-ticket branch unless parking work.
3. **Plan when required** (see column below):
   - Write/approve a short design under `docs/superpowers/specs/`
   - Optionally add an implementation plan under `docs/superpowers/plans/`
   - Do **not** start code until the plan is agreed
4. **Implement** on `backlog-cleanup` (quality gates still apply).
5. **Commit** on `backlog-cleanup`; mark status here. Push the branch when
   useful for backup/review.
6. **End of batch:** open one PR `backlog-cleanup` → `main`, merge, then
   start a fresh backlog branch from `main` if more tickets remain.

Tickets marked **Plan first** need research or a design doc before coding.
Tickets marked **Discuss then code** can skip a formal spec if the chat
agreement is enough.

Work **one ticket at a time** on this branch to keep history readable and
avoid half-finished mixing.

## Suggested order

| Order | ID | Title | Plan first? |
|------:|----|-------|-------------|
| 1 | T2.1 | Auth state flash after login | Discuss then code |
| 2 | T2.2 | Chat does not reset on re-login | Discuss then code |
| 3 | T2.6 | Dark-mode chat glow too strong | Discuss then code |
| 4 | T7 | HITL confirmation bubble redesign | Discuss then code (light design OK) |
| 5 | T2.3 | Settings shown in more than one place | Done |
| 6 | T4 | Library updates live during scraping | Discuss then code |
| 7 | T3 | Login page full redesign | Discuss then code (visual direction) |
| 8 | T2.4 | Admin backoffice visual + UX | Discuss then code |
| 9 | T2.5 | Chat fullscreen redesign + placeholders | Plan first (layout) |
| 10 | T5 | Polling → SSE / push where useful | Plan first (inventory + design) |
| 11 | T1 | Improve book discovery / sources | Plan first (source strategy) |
| 12 | T6 | Full i18n + chat RTL/LTR | Plan first (i18n approach) |

Order can change; finish or park the current ticket before starting the next
on `backlog-cleanup`.

---

## Tickets

### T1 — Improve book discovery / sources

| Field | Value |
|-------|--------|
| Status | Open |
| Branch | _(create when starting)_ |
| Plan first | **Yes** — design + source choice before build |
| Spec / plan | TBD under `docs/superpowers/` |

**Goal:** Better “find books like X / theme search” without guessing titles
or burning the external-tool budget.

**Notes:**
- Prefer an index site with a usable search (e.g. NovelUpdates / Novel Index
  style) → then cross-match to scrapable adapters.
- Free-form web search is a last resort, not the primary path.
- Aligns with the existing “batched theme/trope discovery” roadmap item in
  `docs/llm-planning/06-roadmap-and-sequencing.md` and README discovery
  limitation notes.

**Acceptance (draft):**
- Agreed discovery strategy documented.
- Recommendation-style prompts do not require one external tool call per
  guessed title.
- Results can be crossed with supported scrape sources for import/HITL.

---

### T2 — UI / state / chat / admin polish

Parent of T2.1–T2.6. All sub-tickets commit on `backlog-cleanup`.

#### T2.1 — Auth state flash after login

| Field | Value |
|-------|--------|
| Status | Done |
| Branch | `backlog-cleanup` |
| Plan first | No |

**Problem:** After login, the UI briefly shows the previous user’s data.

**Acceptance (draft):** Logout/login clears or invalidates cached user-owned
server state (react-query) and any client UI state that can leak identity
before the new session’s data loads. Assistant panel closes (not left open).

#### T2.2 — Chat does not reset on re-login

| Field | Value |
|-------|--------|
| Status | Done |
| Branch | `backlog-cleanup` |
| Plan first | No |

**Problem:** Assistant/chat state survives re-login and can show another
user’s conversation context.

**Acceptance (draft):** Auth change clears conversation id, messages,
HITL/pending UI, and related query caches so a new session starts clean.
Panel `open` resets to closed (default app state).

#### T2.3 — Settings shown in more than one place

| Field | Value |
|-------|--------|
| Status | Done |
| Branch | `backlog-cleanup` |
| Plan first | No — inventory + decide keep/remove in chat first |

**Problem:** Some settings appear in multiple UI surfaces; redundant or
confusing.

**Acceptance:** Settings sheet = font size, highlight mode, speech engine,
voice (and server provider), auto-advance to next chapter — with tooltips.
Reader bar keeps speed + volume only. Theme stays in shell sun/moon (not
Settings). Max TTS speed cap removed from Settings UI (store default still
caps the speed slider).

#### T2.4 — Admin backoffice visual + UX

| Field | Value |
|-------|--------|
| Status | Open |
| Branch | _(create when starting)_ |
| Plan first | Discuss visual direction; formal spec only if scope grows |

**Goal:** Improve `/admin/*` look and interaction (density, hierarchy,
empty states, consistency with shared form/query primitives).

#### T2.5 — Chat fullscreen redesign + placeholders

| Field | Value |
|-------|--------|
| Status | Open |
| Branch | _(create when starting)_ |
| Plan first | **Yes** — layout for history / settings / usage |

**Goal:** Fullscreen chat looks intentional; placeholders (or real panels)
for chat history, settings, and usage in that shell.

#### T2.6 — Dark-mode chat glow too strong

| Field | Value |
|-------|--------|
| Status | Done |
| Branch | `backlog-cleanup` |
| Plan first | No |

**Goal:** Soften excessive violet bloom on the assistant panel in dark mode
(keep accent; no neon). Light mode: violet border tint + neutral elevation
only. Nav button and thinking composer left unchanged.

---

### T3 — Login page full redesign

| Field | Value |
|-------|--------|
| Status | Open |
| Branch | _(create when starting)_ |
| Plan first | Discuss visual direction; optional short design note |

**Goal:** Full redesign of the Google SSO login page (brand, layout,
atmosphere). Keep the existing OAuth popup flow unless bugs appear.

---

### T4 — Library updates live during scraping

| Field | Value |
|-------|--------|
| Status | Open |
| Branch | _(create when starting)_ |
| Plan first | No — verify event/query path in chat first |

**Problem:** During scraping, new books can appear but chapter counts do
not update dynamically while the job runs.

**Acceptance (draft):** While a scrape is in progress, library / book
chapter counts refresh so the user sees progress without a full page reload.
May interact with T5 if push is preferred over refetch-on-poll.

---

### T5 — Polling → SSE / push where useful

| Field | Value |
|-------|--------|
| Status | Open |
| Branch | _(create when starting)_ |
| Plan first | **Yes** — inventory pollers, choose keep / SSE / hybrid |

**Goal:** Replace or reduce polling with SSE (or similar) where UX or load
benefits.

**Plan should cover:** download jobs, scrape jobs, EPUB import, in-chat
download cards, admin jobs monitor, any other pollers; per-surface
recommendation; security/authz for streams.

---

### T6 — Full i18n + chat RTL/LTR

| Field | Value |
|-------|--------|
| Status | Open |
| Branch | _(create when starting)_ |
| Plan first | **Yes** — library choice, key structure, RTL rules |

**Goal:**
- Site-wide i18n foundation (even strings that stay English for now).
- Chat: direction from first strong character (RTL vs LTR) per message and
  input; bubble and composer layout adapt at message level.

**Hebrew chat support** is the primary product driver; full-site i18n is
the structural requirement.

---

### T7 — HITL confirmation bubble redesign

| Field | Value |
|-------|--------|
| Status | Done |
| Branch | `backlog-cleanup` |
| Plan first | Discuss then code; short visual notes OK |

**Problems:**
- HITL confirmation UI looks poor.
- Scrape / import confirmation does not show the **book title**.
- Bubble shows too much or the wrong information.

**Goal:** Redesign the confirmation card: clear hierarchy, only required
decision info, Approve / Cancel. For scrape / import tools, show book title
(and short source if useful). Hide noise (raw UUIDs, redundant args).

**Acceptance (draft):**
- Scrape/import HITL shows a human-readable book title.
- Form fields remain editable where required (chapter range, etc.).
- Card works in light and dark mode and fits the chat column.

---

## Status legend

| Status | Meaning |
|--------|---------|
| Open | Not started |
| Planning | Spec/plan in progress |
| In progress | Branch exists; implementation underway |
| Blocked | Waiting on decision or dependency |
| Done | Merged to `main` |

## Related docs

- Discovery / theme search (product intent): `docs/llm-planning/06-roadmap-and-sequencing.md`
- HITL protocol: `docs/llm-planning/04-hitl.md`
- Assistant capabilities (user-facing): `docs/assistant-capabilities.md`
- Existing design/plan pattern: `docs/superpowers/specs/`, `docs/superpowers/plans/`
