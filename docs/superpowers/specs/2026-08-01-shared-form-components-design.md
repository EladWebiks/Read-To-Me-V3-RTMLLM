# Shared Form Components — Design

Date: 2026-08-01
Status: approved

## 1. Goal

Form markup is copy-pasted across the frontend. Extract the repeated pieces
into `shared/ui` and adopt them across the admin feature.

The duplication today, measured:

- **47 `<input>`/`<Input>` across 29 files.** Six of them bypass shared `Input`
  entirely and hand-roll a class string.
- **~20 `text-destructive` error paragraphs**, each repeating the same null
  guard and, for react-query mutations, the same `x.error.message` unwrap.
- **A private `Labeled` helper in `ScrapeDialogFields`** — the shared component
  this design adds, invented locally because it did not exist.
- **No field anywhere wires `aria-describedby` to its error**, and only
  `QuotaSection` sets `aria-invalid`. An errored field is currently invisible
  to a screen reader.

Non-goal: a form library. There is no react-hook-form here and this design does
not introduce one. State stays where it is; only markup and ARIA move.

## 2. Components

All three live in `shared/ui/` and are exported from the barrel.

### 2.1 `FormError`

```tsx
type Props = {
  error?: string | Error | null
  id?: string
  inline?: boolean
  className?: string
}
```

Renders nothing when `error` is falsy. Otherwise a `<p role="alert">` with
`text-xs text-destructive`.

`inline` renders a `<span>` instead. `TierDeactivate` puts its error inside a
`<span>` row, where a `<p>` would be invalid nesting — phrasing content cannot
contain flow content. Each call site is checked against its container during
adoption rather than assumed.

Accepting `Error` is the point: every react-query call site currently writes
`{save.error ? <p …>{save.error.message}</p> : null}`. With this it is
`<FormError error={save.error} />`. `role="alert"` is new behaviour — no
existing error text announces itself.

`id` lets a field point at it via `aria-describedby`.

### 2.2 `TextField`

```tsx
type Props = Omit<InputHTMLAttributes<HTMLInputElement>, 'id'> & {
  id: string
  label: ReactNode
  hint?: ReactNode
  error?: string | Error | null
  numeric?: boolean
}
```

`Label` + `Input` + optional hint + optional error as one unit, forwarding all
remaining native props so `type`, `min`, `pattern`, `required`, `placeholder`
and `autoFocus` keep working.

It owns the ARIA wiring that call sites keep forgetting:

- `<Label htmlFor={id}>`, `<Input id={id}>`
- `aria-invalid={Boolean(error)}`
- `aria-describedby` listing `${id}-hint` and `${id}-error`, whichever exist

`numeric` applies `inputMode="decimal"` and `tabular-nums` — precisely the
hand-rolled string in `PolicyField` and `QuotaSection`. It is orthogonal to
`type="number"`; callers wanting a spinner still pass that.

### 2.3 `FormField`

Same wrapper without the input, for controls `TextField` cannot own: the
`textarea` in `TierFormFields`, file inputs, custom editors. Renders the label,
hint and error, and emits deterministic `${id}-hint` / `${id}-error` ids for the
caller to reference from its own control.

### 2.4 `Input` gains a `size` variant

```tsx
size?: 'default' | 'sm'   // default: 'default'
```

`sm` is the compact inline style used inside tables and inline editors:
`h-7 rounded px-1.5 py-0.5 text-xs`. Width and font stay caller-supplied
(`className="w-20"`, `font-mono`).

This exists because three inline editors each invented their own near-identical
compact style and none used shared `Input`:

| file             | current class string                                       |
| ---------------- | ---------------------------------------------------------- |
| `DraftFields`    | `rounded border border-border bg-background px-2 py-1 text-sm` |
| `PricingCells`   | `w-20 rounded border border-border bg-background px-1.5 py-0.5 text-xs` |
| `ValueEditor`    | `w-48 rounded border border-border bg-background px-1.5 py-0.5 font-mono text-xs` |

## 3. Two kinds of field, deliberately

Not every input gets a visible label. The admin has table-cell and inline
editors that identify themselves with `aria-label` and would break if a
`<Label>` were stacked above them.

- **Labelled fields** → `TextField` (or `FormField` for non-input controls).
- **Inline / table editors** → `Input size="sm"` with `aria-label`, plus
  `FormError` for their mutation errors. They keep no visible label.

Forcing the second group through `TextField` would add a label row inside
`<td>`s and inside the settings row editor. It is not done.

## 4. Adoption — 16 admin files

| file                | change                                        |
| ------------------- | --------------------------------------------- |
| `QuotaSection`      | `TextField` (numeric) + `FormError`           |
| `PolicyField`       | `TextField` (numeric)                         |
| `TierFormFields`    | `TextField` ×4, `FormField` for the textarea  |
| `UserQuotasDialog`  | `TextField` + `FormError`                     |
| `DraftFields`       | `Input size="sm"`                             |
| `PricingCells`      | `Input size="sm"` + `FormError`               |
| `ValueEditor`       | `Input size="sm"` + `FormError`               |
| `TierFormDialog`    | `FormError`                                   |
| `TierActions`       | `FormError`                                   |
| `TierDeactivate`    | `FormError inline` (lives in a `<span>` row)  |
| `UserRowActions`    | `FormError`                                   |
| `AddModelForm`      | `FormError`                                   |
| `ModelRow`          | `FormError`                                   |
| `ProviderSection`   | `FormError`                                   |
| `SettingRow`        | `FormError`                                   |
| `PolicyCard`        | `FormError` (its form-level message)          |

Page-level states such as `<p>Failed to load users.</p>` are not form errors
and are left alone.

Features outside `admin` (library, scraping, downloads, reader, assistant) are
out of scope for this pass, including the duplicate `Labeled` helper in
`ScrapeDialogFields`. They can adopt the same components later.

## 5. Visual changes

Two, both intended:

1. **Policy and quota grids get taller.** `PolicyField` and `QuotaSection` move
   from bespoke `px-2 py-1` inputs and muted inline `<span>` labels to the
   standard `h-9` `Input` and `Label`. A tier card carries 7 policy fields plus
   the quota fields, so expect roughly 40% more height per card.
2. **The three inline editors normalise onto one compact size.** `DraftFields`
   shrinks slightly (`text-sm` → `text-xs`, `px-2 py-1` → `px-1.5 py-0.5`);
   `PricingCells` and `ValueEditor` keep their current look.

Everything else renders as it does today.

## 6. Testing

New `shared/ui/form-field.test.tsx` covering, written before the components:

- label is associated with the control (`getByLabelText` finds it)
- an error sets `aria-invalid`, renders `role="alert"`, and is referenced by
  `aria-describedby`
- a hint is referenced by `aria-describedby`; both hint and error are listed
  when both exist
- no error → no alert node at all
- `FormError` unwraps an `Error` to its message and renders nothing for
  `null` / `undefined` / `''`
- `numeric` sets `inputMode`
- `FormField` exposes the ids its caller needs

The 13 existing admin test files are the regression net for adoption. They
query by placeholder, display value, role and text, so they should pass
unchanged. Any that do not get shown to the user rather than quietly rewritten
— a test that needs editing here is evidence of a behaviour change, not a
formality.

## 7. Out of scope

- Per-field validation errors for policy fields. `PolicyCard` keeps its
  form-level "Enter numbers (or blank)." message. Giving each policy field its
  own error the way quotas now have is a behaviour change, not an extraction.
- Any form library or validation framework.
- Non-admin features.

## 8. Risks

- **`TextField` prop sprawl.** Spreading native input props is convenient but
  makes the component a passthrough. Accepted: the alternative is a render prop
  at every call site, which is worse for the 90% case.
- **Grid height.** The policy page becomes noticeably taller. This was chosen
  explicitly over keeping a second density variant.
- **`size` on `Input` is a second axis.** Kept to two values. If a third
  appears, that is the signal to reach for a variants helper like the existing
  `buttonVariants`, not to keep adding strings.
