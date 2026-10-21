# T6 — i18n foundation + per-message chat direction

Date: 2026-08-04
Status: Approved (implementing)

## Goal

Hebrew chat support as the product driver: messages and the composer adapt
direction from the first strong character. Install a site-wide i18n
foundation so future locales are a translation task, not a refactor.

## Locked decisions

- **RTL scope:** chat only. App shell stays English / LTR. No app-wide
  `dir=rtl` mirroring, no Hebrew UI translations yet.
- **HITL copy:** stays English for now. HITL cards still use `dir="auto"` on
  dynamic values (e.g. Hebrew book titles) so those render correctly.
- **i18n foundation:** `i18next` + `react-i18next`, English namespaces only.
  Assistant + shell copy migrated first; other features follow later.

## Direction mechanism

Use native HTML `dir="auto"` (Unicode first-strong bidi paragraph rule).
Skips neutrals (whitespace, digits, markdown punctuation) and picks LTR/RTL
from the first strong letter. Re-evaluates live in `<textarea>`, so the
composer flips as the user types.

Applied to: user bubble, assistant prose (`.assistant-md`), composer textarea,
tool-card summaries, HITL headline/subtitle, choice chips, history titles,
live status / error text.

User bubbles keep `justify-end` (identity alignment, not text direction).

## Logical CSS

`.assistant-md` list and blockquote padding/borders use
`padding-inline-start` / `border-inline-start`. HITL accent uses
`border-s-*`. Assistant physical utilities audited to logical where they
affect RTL text.

## Backend

`SYSTEM_PROMPT` Conduct: reply in the same language the user writes in;
keep book titles and tool-provided values as returned. No backend locale
header; HITL step lines remain English.

## Out of scope

Hebrew UI translation, app-wide RTL mirroring, admin i18n, backend-localized
HITL labels.

## Acceptance

- Typing Hebrew in the composer flips input to RTL; English stays LTR.
- User and assistant messages with Hebrew content render RTL.
- HITL dynamic titles with Hebrew characters render correctly.
- English UI strings for assistant/shell come from i18n catalogs.
- Quality gates green.
