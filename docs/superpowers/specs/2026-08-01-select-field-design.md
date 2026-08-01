# Shared Select Components — Design

Date: 2026-08-01
Status: proposed

## 1. Goal

Every `<select>` in the app is hand-rolled. Add `Select` and `SelectField` to
`shared/ui` as exact siblings of `Input` / `TextField`, and adopt them.

This also unblocks the gap left by
`2026-08-01-shared-form-components-design.md`: three admin selects
(`TierDeactivate`, `ToolCallFilters`, `UserRow`) are the reason the "no
hand-rolled control styles in admin" check could not come back clean.

### 1.1 The duplication, measured

Thirteen selects across ten files, with **six different paddings** for what is
visually the same control:

| file | class string |
| ---- | ------------ |
| `VoicePickers` (×3) | `rounded-md border border-border bg-background px-2 py-1 text-foreground` |
| `PlayerControls` | `rounded-md border border-border bg-background px-2 py-1 text-foreground` |
| `DownloadFields` | `rounded-md border border-border bg-background px-2 py-1 text-foreground` |
| `AudioModalSelects` (×2) | `rounded-md border border-border bg-background px-2 py-1.5 text-foreground` |
| `ReaderBottomBar` | `min-w-[12rem] flex-1 rounded-md border border-input bg-background px-3 py-1.5 text-sm` |
| `ConfirmationFields` | `w-full rounded-lg border border-border bg-background px-2.5 py-1.5 text-sm` |
| `ConfirmationVoiceControl` | `w-full rounded-lg border border-border bg-background px-2.5 py-1.5 text-sm` |
| `ToolCallFilters` | `rounded border border-border bg-background px-2 py-1 text-sm` |
| `TierDeactivate` | `rounded border border-border bg-background px-1 py-0.5` |
| `UserRow` | `rounded border border-border bg-background px-1 py-0.5 text-xs` |

None of them wire a label properly: the reader and download selects use a
wrapping `<label>` with no `htmlFor`/`id`, and the admin ones rely on
`aria-label`. None can show a validation error.

**`ReaderBottomBar` uses `border-input`, which is not a token this app
defines.** `@theme inline` in `index.css` maps `--color-border` and
`--color-ring` but nothing named `input`, so that utility generates no colour;
the element only looks right because the global `* { border-color: var(--border) }`
rule catches it. Harmless today, invisible until someone changes that global.
It is exactly the class of drift a shared component prevents, and adopting
`Select` fixes it as a side effect.

## 2. Components

### 2.1 `Select`

```tsx
type Props = Omit<SelectHTMLAttributes<HTMLSelectElement>, 'size'> & {
  size?: 'default' | 'sm'
}
```

Same two-variant shape as `Input`, sharing its size strings so a `Select` and
an `Input` sitting side by side line up:

- `default` — `h-9 w-full rounded-md border border-border bg-background px-3 py-1 text-sm …`
- `sm` — `h-7 rounded border border-border bg-background px-1.5 py-0.5 text-xs …`

**The `size` collision is deliberate and must be handled the same way as
`Input`.** Native `<select size={n}>` sets the visible row count; we shadow it
with the variant name and `Omit` the native one. No call site uses it. If one
ever needs it, the escape hatch is `<select>` directly, not widening the type.

Native appearance is kept — no `appearance-none` plus custom chevron. The
whole app uses native selects today; replacing the chevron means owning
cross-browser arrow rendering for zero functional gain. Out of scope, and
noted here so the omission reads as a decision rather than an oversight.

### 2.2 `SelectField`

```tsx
type Props = Omit<SelectHTMLAttributes<HTMLSelectElement>, 'id' | 'size'> & {
  id: string
  label: ReactNode
  hint?: ReactNode
  error?: string | Error | null
  children: ReactNode   // <option> elements
}
```

Composes the existing `FormField` exactly as `TextField` does, and reuses
`describedBy` from `shared/ui/field-aria.ts` — `htmlFor`/`id`, `aria-invalid`
when errored, `aria-describedby` listing `${id}-hint` and `${id}-error`.

Options stay as `children`. An `options={[{value,label}]}` convenience prop was
considered and dropped: the eleven call sites disagree on option shape
(`{id,name}`, `{slug,label}`, `{value,label}`, literal pairs) and four prepend
a placeholder option (`Default`, `Any risk`). `children` covers all of it with
no mapping layer.

### 2.3 Where the label goes

Same split as the input work — two legitimate kinds of control:

- **Labelled** → `SelectField`.
- **Inline / table** → `Select` with `aria-label`, no visible label.

## 3. Adoption — 10 files

| file | change |
| ---- | ------ |
| `TierDeactivate` | `Select size="sm"`, keeps `aria-label` (inline `<span>` row) |
| `UserRow` | `Select size="sm"`, keeps `aria-label` (table cell) |
| `ToolCallFilters` | `Select size="sm"`, keeps `aria-label` (filter bar) |
| `AudioModalSelects` | `SelectField` ×2 — already stacked label + control |
| `DownloadFields` | `Select` + wrapping label kept (inline `items-center` row) |
| `VoicePickers` | `Select` ×3 + wrapping labels kept (player bar, inline) |
| `PlayerControls` | `Select` + wrapping label kept (player bar, inline) |
| `ReaderBottomBar` | `Select`, keeps `aria-label` and `min-w-[12rem] flex-1`; drops the dead `border-input` |
| `ConfirmationFields` | `Select`, `w-full` via className |
| `ConfirmationVoiceControl` | `Select`, `w-full` via className |

This is the complete list — a `<select` search over `src/` returns these ten
files and no others. `JobsPage` and `SearchSortBar` hold `<input>` and buttons
respectively, not selects.

### 3.1 The inline-label call sites

`VoicePickers` and `DownloadFields` wrap their select in
`<label className="flex items-center gap-1">Voice <select/></label>` — a
horizontal player-bar layout that `SelectField`'s stacked block would break.
They keep their wrapping label and adopt only `Select`. Implicit
label association already works there; this design does not regress it, and
converting those two layouts is a separate visual change.

## 4. Visual changes

The five paddings collapse to two heights. Concretely:

- Reader player and download selects go from `py-1` to the standard `h-9` —
  **the player bar gets slightly taller**. This is the one visible change and
  the one to check before merging.
- `ConfirmationFields` / `ConfirmationVoiceControl` go from `rounded-lg` to
  `rounded-md`, matching every other control in the assistant panel.
- Admin selects (`px-1 py-0.5`, `px-2 py-1`) land on `sm` — near-identical.

If the player bar height turns out to matter, the fix is to pass
`size="sm"` there rather than to reintroduce a third variant.

## 5. Testing

Extend `shared/ui/form-field.test.tsx` (it already covers the field family):

- `SelectField` associates its label with the select (`getByLabelText` returns
  a `SELECT`)
- an error sets `aria-invalid`, renders `role="alert"`, and is referenced by
  `aria-describedby`
- hint and error ids are both listed, hint first
- no error → no `aria-invalid`, no alert node
- `children` options render and the current `value` is selected
- `Select size="sm"` uses the compact style; `default` uses `h-9`
- native props (`disabled`, `required`, `name`) are forwarded

Regression net for adoption: `TierDeactivate.test.tsx`, `UsersPage.test.tsx`,
`ToolCallsPage`-related tests and the reader/download suites. They query by
`aria-label` and display value, so they should pass unchanged. A test that
needs editing is evidence of a behaviour change — stop and report it.

## 6. Out of scope

- A custom listbox (Radix Select or similar). Native `<select>` keeps mobile
  behaviour, keyboard support and zero bundle cost. Revisit only if a design
  needs option groups with rich content.
- Multi-select.
- `SearchSortBar` sort controls if they turn out to be buttons rather than a
  select.
