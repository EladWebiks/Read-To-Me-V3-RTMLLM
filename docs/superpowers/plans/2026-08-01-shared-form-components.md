# Shared Form Components Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extract `FormError`, `TextField`, `FormField` and an `Input` size variant into `shared/ui`, then adopt them across the 16 admin form files.

**Architecture:** Pure markup/ARIA extraction — no form library, no state changes. Spec: `docs/superpowers/specs/2026-08-01-shared-form-components-design.md`. Components compose the existing `Input`/`Label`; call sites keep their `useState`/react-query wiring untouched.

**Tech Stack:** React 19 + TypeScript, Tailwind, vitest + @testing-library/react (globals:false — always import from vitest and register `afterEach(cleanup)`).

## Global Constraints

- All commands run from `frontend/` unless stated otherwise.
- ESLint hard limits: file ≤ 110 lines, function ≤ 60 lines, nesting ≤ 3. Test files and barrels are exempt.
- Strict TS, no `any`. Prettier is enforced through eslint; if `npm run lint` reports prettier errors, run `npx eslint . --fix` (the standalone `npm run format` does not always satisfy the eslint prettier plugin).
- Commit with `bash scripts/git-commit-clean.sh <msg-file>` from the repo root (never `git commit -m`). NEVER add `Co-authored-by`/`Made-with` trailers.
- Gate for every task: `npm run lint` && `npm run build` && `npm run test` all pass.
- Do not change behaviour of any call site beyond what a task states. If an existing test fails after adoption, STOP and report — do not rewrite the test to fit.

## File Structure

```
frontend/src/shared/ui/
  form-error.tsx        # NEW  FormError
  form-field.tsx        # NEW  FormField + describedBy helper
  text-field.tsx        # NEW  TextField (composes FormField + Input)
  form-field.test.tsx   # NEW  covers all three + Input size variant
  input.tsx             # MODIFIED  size: 'default' | 'sm'
  index.ts              # MODIFIED  barrel exports
```

Adoption (all under `frontend/src/features/admin/components/`): `policies/` QuotaSection, PolicyField, PolicyCard, TierFormFields, TierFormDialog, TierActions, TierDeactivate · `users/` UserQuotasDialog, UserRowActions · `catalog/` DraftFields, PricingCells, ModelRow, ProviderSection, AddModelForm · `settings/` ValueEditor, SettingRow.

---

### Task 1: `FormError` + `Input size` variant

**Files:**
- Create: `frontend/src/shared/ui/form-error.tsx`
- Create: `frontend/src/shared/ui/form-field.test.tsx`
- Modify: `frontend/src/shared/ui/input.tsx`
- Modify: `frontend/src/shared/ui/index.ts`

**Interfaces:**
- Consumes: `cn` from `@/shared/lib/cn`.
- Produces: `FormError({ error?: string | Error | null, id?: string, inline?: boolean, className?: string })` — renders `null` when no message; else `<p role="alert">` (`<span>` when `inline`) with `text-xs text-destructive`. `Input` gains `size?: 'default' | 'sm'` (native numeric `size` attr is dropped from the prop type; nothing in the repo uses it).

- [ ] **Step 1: Write the failing tests**

Create `frontend/src/shared/ui/form-field.test.tsx`:

```tsx
import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'
import { FormError } from './form-error'
import { Input } from './input'

// vitest runs with globals:false, so testing-library's auto-cleanup is not registered.
afterEach(cleanup)

describe('FormError', () => {
  it('renders nothing for null, undefined and empty string', () => {
    expect(render(<FormError error={null} />).container.innerHTML).toBe('')
    expect(render(<FormError />).container.innerHTML).toBe('')
    expect(render(<FormError error="" />).container.innerHTML).toBe('')
  })

  it('renders a string error as an alert paragraph', () => {
    render(<FormError error="Nope." />)
    const alert = screen.getByRole('alert')
    expect(alert.textContent).toBe('Nope.')
    expect(alert.tagName).toBe('P')
    expect(alert.className).toContain('text-destructive')
  })

  it('unwraps an Error to its message', () => {
    render(<FormError error={new Error('Server said no')} />)
    expect(screen.getByRole('alert').textContent).toBe('Server said no')
  })

  it('renders a span when inline (for phrasing-content containers)', () => {
    render(<FormError inline error="Nope." />)
    expect(screen.getByRole('alert').tagName).toBe('SPAN')
  })

  it('takes an id so fields can reference it', () => {
    render(<FormError id="f-error" error="Bad" />)
    expect(screen.getByRole('alert').id).toBe('f-error')
  })
})

describe('Input size', () => {
  it('defaults to the standard h-9 style', () => {
    render(<Input aria-label="standard" readOnly value="" />)
    expect(screen.getByLabelText('standard').className).toContain('h-9')
  })

  it('sm renders the compact inline style', () => {
    render(<Input size="sm" aria-label="compact" readOnly value="" />)
    const className = screen.getByLabelText('compact').className
    expect(className).toContain('h-7')
    expect(className).toContain('text-xs')
    expect(className).not.toContain('w-full') // inline editors size themselves
  })
})
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `npm run test -- src/shared/ui/form-field.test.tsx`
Expected: FAIL — cannot resolve `./form-error`; the `size="sm"` assertion also fails.

- [ ] **Step 3: Implement `FormError`**

Create `frontend/src/shared/ui/form-error.tsx`:

```tsx
import { cn } from '@/shared/lib/cn'

type Props = {
  error?: string | Error | null
  id?: string
  /** Render a <span>: for containers that only allow phrasing content. */
  inline?: boolean
  className?: string
}

/** Standard destructive error line; renders nothing when there is no error. */
export function FormError({ error, id, inline = false, className }: Props) {
  const message = typeof error === 'string' ? error : (error?.message ?? '')
  if (!message) return null
  const Tag = inline ? 'span' : 'p'
  return (
    <Tag id={id} role="alert" className={cn('text-xs text-destructive', className)}>
      {message}
    </Tag>
  )
}
```

- [ ] **Step 4: Implement the `Input` size variant**

Replace the body of `frontend/src/shared/ui/input.tsx` with:

```tsx
import type { InputHTMLAttributes } from 'react'
import { cn } from '@/shared/lib/cn'

type Props = Omit<InputHTMLAttributes<HTMLInputElement>, 'size'> & {
  /** 'sm' is the compact inline-editor style (tables, in-row editors). */
  size?: 'default' | 'sm'
}

const SIZES = {
  default:
    'flex h-9 w-full rounded-md border border-border bg-background px-3 py-1 text-sm shadow-sm transition-colors placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50',
  sm: 'h-7 rounded border border-border bg-background px-1.5 py-0.5 text-xs placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50',
}

export function Input({ className, type = 'text', size = 'default', ...props }: Props) {
  return <input type={type} className={cn(SIZES[size], className)} {...props} />
}
```

- [ ] **Step 5: Export from the barrel**

In `frontend/src/shared/ui/index.ts` replace `export { Input } from './input'` with:

```ts
export { FormError } from './form-error'
export { Input } from './input'
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `npm run test -- src/shared/ui/form-field.test.tsx`
Expected: PASS (7 tests).

- [ ] **Step 7: Gate and commit**

Run: `npm run lint && npm run build && npm run test`
Expected: all pass; full suite still 143 tests green.

From the repo root, write the message to a temp file and commit:

```
feat: add shared FormError and a compact Input size variant

FormError replaces the hand-written text-destructive paragraphs (and
their error.message unwrapping); role="alert" is new. Input size="sm"
is the inline-editor style three admin files each hand-rolled.
```

Run: `git add -A && bash scripts/git-commit-clean.sh <msg-file>`

---

### Task 2: `FormField` + `TextField`

**Files:**
- Create: `frontend/src/shared/ui/form-field.tsx`
- Create: `frontend/src/shared/ui/text-field.tsx`
- Modify: `frontend/src/shared/ui/form-field.test.tsx`
- Modify: `frontend/src/shared/ui/index.ts`

**Interfaces:**
- Consumes: `FormError` (Task 1), `Input` (Task 1), `Label`, `cn`.
- Produces:
  - `FormField({ id: string, label: ReactNode, hint?: ReactNode, error?: string | Error | null, className?: string, children: ReactNode })` — label/hint/error wrapper emitting `${id}-hint` / `${id}-error`.
  - `describedBy(id: string, hasHint: boolean, hasError: boolean): string | undefined` (exported from `./form-field`, not the barrel).
  - `TextField(Omit<InputHTMLAttributes<HTMLInputElement>, 'id' | 'size'> & { id: string, label: ReactNode, hint?: ReactNode, error?: string | Error | null, numeric?: boolean })`.

- [ ] **Step 1: Add the failing tests**

Append to `frontend/src/shared/ui/form-field.test.tsx` (add `FormField`, `TextField` imports):

```tsx
import { FormField } from './form-field'
import { TextField } from './text-field'

describe('TextField', () => {
  it('associates the label with the input', () => {
    render(<TextField id="f" label="AI tokens" readOnly value="" />)
    expect(screen.getByLabelText('AI tokens').tagName).toBe('INPUT')
  })

  it('wires an error to aria-invalid, aria-describedby and an alert', () => {
    render(<TextField id="f" label="L" error="Bad" readOnly value="" />)
    const input = screen.getByLabelText('L')
    expect(input.getAttribute('aria-invalid')).toBe('true')
    expect(input.getAttribute('aria-describedby')).toBe('f-error')
    expect(screen.getByRole('alert').id).toBe('f-error')
  })

  it('accepts an Error object as the error', () => {
    render(<TextField id="f" label="L" error={new Error('boom')} readOnly value="" />)
    expect(screen.getByRole('alert').textContent).toBe('boom')
  })

  it('lists hint and error ids in aria-describedby, hint first', () => {
    render(<TextField id="f" label="L" hint="H" error="E" readOnly value="" />)
    const input = screen.getByLabelText('L')
    expect(input.getAttribute('aria-describedby')).toBe('f-hint f-error')
    expect(document.getElementById('f-hint')?.textContent).toBe('H')
  })

  it('adds no aria noise when healthy', () => {
    render(<TextField id="f" label="L" readOnly value="" />)
    const input = screen.getByLabelText('L')
    expect(input.getAttribute('aria-invalid')).toBeNull()
    expect(input.getAttribute('aria-describedby')).toBeNull()
    expect(screen.queryByRole('alert')).toBeNull()
  })

  it('numeric sets decimal inputMode and tabular numerals', () => {
    render(<TextField id="f" label="L" numeric readOnly value="" />)
    const input = screen.getByLabelText('L')
    expect(input.getAttribute('inputmode')).toBe('decimal')
    expect(input.className).toContain('tabular-nums')
  })

  it('forwards native input props', () => {
    render(<TextField id="f" label="L" type="number" min={1} placeholder="p" readOnly value="" />)
    const input = screen.getByLabelText('L')
    expect(input.getAttribute('type')).toBe('number')
    expect(input.getAttribute('min')).toBe('1')
    expect(input.getAttribute('placeholder')).toBe('p')
  })
})

describe('FormField', () => {
  it('labels a caller-rendered control and exposes hint/error ids', () => {
    render(
      <FormField id="d" label="Description" hint="Optional" error="Too long">
        <textarea id="d" aria-describedby="d-hint d-error" />
      </FormField>,
    )
    expect(screen.getByLabelText('Description').tagName).toBe('TEXTAREA')
    expect(document.getElementById('d-hint')?.textContent).toBe('Optional')
    expect(document.getElementById('d-error')?.textContent).toBe('Too long')
    expect(screen.getByRole('alert').id).toBe('d-error')
  })

  it('renders no hint or error nodes when it has none', () => {
    render(
      <FormField id="d" label="Description">
        <textarea id="d" />
      </FormField>,
    )
    expect(document.getElementById('d-hint')).toBeNull()
    expect(screen.queryByRole('alert')).toBeNull()
  })
})
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `npm run test -- src/shared/ui/form-field.test.tsx`
Expected: FAIL — cannot resolve `./form-field` / `./text-field`.

- [ ] **Step 3: Implement `FormField`**

Create `frontend/src/shared/ui/form-field.tsx`:

```tsx
import type { ReactNode } from 'react'
import { cn } from '@/shared/lib/cn'
import { FormError } from './form-error'
import { Label } from './label'

type Props = {
  id: string
  label: ReactNode
  hint?: ReactNode
  error?: string | Error | null
  className?: string
  children: ReactNode
}

/** aria-describedby value for a field with this id; undefined when bare. */
export function describedBy(
  id: string,
  hasHint: boolean,
  hasError: boolean,
): string | undefined {
  const ids = [hasHint ? `${id}-hint` : null, hasError ? `${id}-error` : null]
  const present = ids.filter((part): part is string => part !== null)
  return present.length > 0 ? present.join(' ') : undefined
}

/** Label + hint + error around a control the CALLER renders (textarea, file…).
 *
 * Emits `${id}-hint` / `${id}-error`; wire them to the control with
 * `describedBy` (TextField does all of this automatically).
 */
export function FormField({ id, label, hint, error, className, children }: Props) {
  return (
    <div className={cn('space-y-1', className)}>
      <Label htmlFor={id}>{label}</Label>
      {children}
      {hint != null ? (
        <p id={`${id}-hint`} className="text-xs text-muted-foreground">
          {hint}
        </p>
      ) : null}
      <FormError id={`${id}-error`} error={error} />
    </div>
  )
}
```

- [ ] **Step 4: Implement `TextField`**

Create `frontend/src/shared/ui/text-field.tsx`:

```tsx
import type { InputHTMLAttributes, ReactNode } from 'react'
import { cn } from '@/shared/lib/cn'
import { describedBy, FormField } from './form-field'
import { Input } from './input'

type Props = Omit<InputHTMLAttributes<HTMLInputElement>, 'id' | 'size'> & {
  id: string
  label: ReactNode
  hint?: ReactNode
  error?: string | Error | null
  /** Decimal inputMode + tabular numerals (admin numeric fields). */
  numeric?: boolean
}

/** Label + Input + hint + error as one unit, with the ARIA wiring done. */
export function TextField({
  id,
  label,
  hint,
  error,
  numeric = false,
  className,
  inputMode,
  ...props
}: Props) {
  const hasError = error != null && error !== ''
  return (
    <FormField id={id} label={label} hint={hint} error={error}>
      <Input
        {...props}
        id={id}
        inputMode={numeric ? 'decimal' : inputMode}
        aria-invalid={hasError ? true : undefined}
        aria-describedby={describedBy(id, hint != null, hasError)}
        className={cn(numeric && 'tabular-nums', className)}
      />
    </FormField>
  )
}
```

- [ ] **Step 5: Export from the barrel**

In `frontend/src/shared/ui/index.ts`, after the `FormError` line add:

```ts
export { FormField } from './form-field'
export { TextField } from './text-field'
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `npm run test -- src/shared/ui/form-field.test.tsx`
Expected: PASS (16 tests).

- [ ] **Step 7: Gate and commit**

Run: `npm run lint && npm run build && npm run test`
Expected: all pass.

Commit message:

```
feat: add shared TextField and FormField with the ARIA wiring done

Label/input association, aria-invalid, and aria-describedby pointing at
the hint and error ids — none of which any admin field wires today.
```

---

### Task 3: Adopt in the quota surfaces (QuotaSection, UserQuotasDialog)

**Files:**
- Modify: `frontend/src/features/admin/components/policies/QuotaSection.tsx`
- Modify: `frontend/src/features/admin/components/users/UserQuotasDialog.tsx`
- Tests (regression net, do NOT edit): `QuotaSection.test.tsx`, `UserQuotasDialog.test.tsx`

**Interfaces:**
- Consumes: `TextField`, `FormError` from `@/shared/ui`; `parseQuotaInput` from `@/features/admin/logic/quotaFields` (unchanged).
- Produces: no API changes; markup only. Field ids: `quota-${membership}-${kind}` in QuotaSection (unique across tier cards), `quota-${kind}` in the dialog (single instance).

- [ ] **Step 1: Convert QuotaSection**

Replace the JSX of `QuotaSection.tsx` — state, `parsed`, `errorFor`, `blocked` and `onSave` stay exactly as they are; only the rendering changes. Full resulting file:

```tsx
import { useState } from 'react'
import type {
  MembershipQuotaRow,
  QuotaKindInfo,
} from '@/features/admin/api/membershipQuotas'
import { useSaveQuota } from '@/features/admin/hooks/useMembershipQuotas'
import { parseQuotaInput } from '@/features/admin/logic/quotaFields'
import { FormError, TextField } from '@/shared/ui'

type Props = { membership: string; kinds: QuotaKindInfo[]; rows: MembershipQuotaRow[] }

function initialDrafts(kinds: QuotaKindInfo[], rows: MembershipQuotaRow[]) {
  const byKind = new Map(rows.map((r) => [r.quota_kind, r.limit_value]))
  return Object.fromEntries(
    kinds.map((k) => [k.kind, byKind.has(k.kind) ? String(byKind.get(k.kind)) : '']),
  )
}

export function QuotaSection({ membership, kinds, rows }: Props) {
  const [drafts, setDrafts] = useState(() => initialDrafts(kinds, rows))
  const save = useSaveQuota()
  const current = new Map(rows.map((r) => [r.quota_kind, r.limit_value]))
  // Derived during render — the draft text is the only source of truth.
  const parsed = new Map(
    kinds.map((k) => [k.kind, parseQuotaInput(drafts[k.kind] ?? '')]),
  )
  const errorFor = (kind: string) => {
    const result = parsed.get(kind)
    return result && !result.ok ? result.error : null
  }
  const blocked = kinds.some((k) => errorFor(k.kind) !== null)

  const onSave = () => {
    for (const meta of kinds) {
      const result = parsed.get(meta.kind)
      if (result?.ok && result.value !== (current.get(meta.kind) ?? null)) {
        save.mutate({ membership, kind: meta.kind, limit: result.value })
      }
    }
  }

  return (
    <div className="mt-3 border-t border-border/60 pt-3">
      <p className="mb-2 text-sm font-medium">Quotas (blank = unlimited, 0 = blocked)</p>
      <div className="grid gap-2 sm:grid-cols-2">
        {kinds.map((meta) => (
          <TextField
            key={meta.kind}
            id={`quota-${membership}-${meta.kind}`}
            label={`${meta.label} (${meta.unit}${meta.window === 'month' ? ' / month' : ', standing'})`}
            numeric
            value={drafts[meta.kind] ?? ''}
            placeholder={current.has(meta.kind) ? '' : 'unlimited'}
            error={errorFor(meta.kind)}
            onChange={(event) =>
              setDrafts((prev) => ({ ...prev, [meta.kind]: event.target.value }))
            }
          />
        ))}
      </div>
      <button
        type="button"
        className="mt-3 rounded-md bg-primary px-3 py-1.5 text-sm text-primary-foreground disabled:opacity-50"
        disabled={save.isPending || blocked}
        onClick={onSave}
      >
        {save.isPending ? 'Saving…' : 'Save quotas'}
      </button>
      <FormError className="mt-2" error={save.error} />
    </div>
  )
}
```

- [ ] **Step 2: Convert UserQuotasDialog**

`QuotaOverrideField` collapses into a direct `TextField`; the `invalid` state and `commit` stay. Full resulting file:

```tsx
import { useState } from 'react'
import { useSetUserQuota, useUserQuotas } from '@/features/admin/hooks/useUserQuotas'
import { parseQuotaInput } from '@/features/admin/logic/quotaFields'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  FormError,
  TextField,
} from '@/shared/ui'

type Props = {
  userId: string
  username: string
  open: boolean
  onOpenChange: (open: boolean) => void
}

/** Registry-driven per-user overrides; they win over the user's tier limits.
 * Blank = tier default (placeholder shows it); a number = override (0 = blocked). */
export function UserQuotasDialog({ userId, username, open, onOpenChange }: Props) {
  const { data } = useUserQuotas(userId, open)
  const save = useSetUserQuota(userId)
  const [invalid, setInvalid] = useState<string | null>(null)
  const overrideOf = (kind: string) =>
    data?.overrides.find((row) => row.quota_kind === kind)?.limit_value

  const commit = (kind: string, raw: string) => {
    const parsed = parseQuotaInput(raw)
    setInvalid(parsed.ok ? null : parsed.error)
    if (!parsed.ok) return
    if (parsed.value === null) {
      if (overrideOf(kind) !== undefined) {
        save.mutate({ kind, limit: null })
      }
      return
    }
    if (parsed.value !== overrideOf(kind)) {
      save.mutate({ kind, limit: parsed.value })
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Quota overrides — {username}</DialogTitle>
        </DialogHeader>
        <p className="text-xs text-muted-foreground">
          Blank uses the {data?.membership ?? ''} tier limit. Admins stay exempt.
        </p>
        <div className="space-y-3">
          {data?.kinds.map((kind) => (
            <TextField
              key={kind.kind}
              id={`quota-${kind.kind}`}
              label={`${kind.label} (${kind.unit})`}
              numeric
              defaultValue={overrideOf(kind.kind) ?? ''}
              placeholder={
                data.tier_limits[kind.kind] === undefined
                  ? 'Unlimited (tier)'
                  : `${data.tier_limits[kind.kind].toLocaleString('en-US')} (tier)`
              }
              onBlur={(event) => commit(kind.kind, event.target.value)}
            />
          ))}
        </div>
        <FormError error={invalid ?? save.error} />
      </DialogContent>
    </Dialog>
  )
}
```

- [ ] **Step 3: Run the regression net**

Run: `npm run test -- src/features/admin/components/policies/QuotaSection.test.tsx src/features/admin/components/users/UserQuotasDialog.test.tsx`
Expected: PASS unchanged (13 tests). These tests query by placeholder, display value and text — if any fails, STOP and report; do not edit the tests.

- [ ] **Step 4: Gate and commit**

Run: `npm run lint && npm run build && npm run test`
Expected: all pass.

Commit message:

```
refactor: adopt TextField/FormError on the quota admin surfaces

Grid inputs converge on the standard h-9 Input per the design spec;
errored quota fields gain aria-describedby and role=alert.
```

---

### Task 4: Adopt in policy + tier files

**Files:**
- Modify: `policies/PolicyField.tsx`, `policies/PolicyCard.tsx`, `policies/TierFormFields.tsx`, `policies/TierFormDialog.tsx`, `policies/TierActions.tsx`, `policies/TierDeactivate.tsx`
- Tests (regression net): `PoliciesPage.test.tsx`, `TierDeactivate.test.tsx`

**Interfaces:**
- Consumes: `TextField`, `FormField`, `FormError` from `@/shared/ui`.
- Produces: `PolicyField` gains a required `membership: string` prop (for unique ids across tier cards); `PolicyCard` passes `policy.membership`. No other signature changes.

- [ ] **Step 1: Convert PolicyField (full file)**

```tsx
import type { PolicyFieldMeta } from '@/features/admin/logic/policyFields'
import { placeholderFor } from '@/features/admin/logic/policyFields'
import { TextField } from '@/shared/ui'

type Props = {
  membership: string
  meta: PolicyFieldMeta
  value: string
  inherited: Record<string, number>
  onChange: (raw: string) => void
}

export function PolicyField({ membership, meta, value, inherited, onChange }: Props) {
  return (
    <TextField
      id={`policy-${membership}-${meta.key}`}
      label={meta.label}
      numeric
      value={value}
      placeholder={placeholderFor(meta, inherited)}
      onChange={(event) => onChange(event.target.value)}
    />
  )
}
```

- [ ] **Step 2: Update PolicyCard**

Three changes:

1. Pass the new prop: `<PolicyField key={meta.key} membership={policy.membership} meta={meta} … />`
2. Replace the `invalid` paragraph with `FormError` (keeps the exact copy):

```tsx
<FormError
  className="mt-2"
  error={invalid ? 'Enter numbers (or blank).' : null}
/>
```

3. After the Save button, surface the mutation error, which today is silently
   swallowed (the same defect class just fixed on the quota surfaces):

```tsx
<FormError className="mt-2" error={mutation.error} />
```

Import: `import { FormError } from '@/shared/ui'`.

- [ ] **Step 3: Convert TierFormFields (full file)**

```tsx
import type { ChangeEvent } from 'react'
import { FormField, TextField } from '@/shared/ui'
import type { TierDraft } from './TierFormDialog'

type Props = {
  showSlug: boolean
  draft: TierDraft
  onChange: (
    key: keyof TierDraft,
  ) => (event: ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => void
}

/** The bare input fields for TierFormDialog's form (slug is create-only). */
export function TierFormFields({ showSlug, draft, onChange }: Props) {
  return (
    <>
      {showSlug ? (
        <TextField
          id="tier-slug"
          label="Slug"
          value={draft.slug}
          pattern="^[a-z0-9_-]{1,32}$"
          title="Lowercase letters, digits, _ or -, up to 32 characters"
          onChange={onChange('slug')}
          required
        />
      ) : null}
      <TextField id="tier-label" label="Label" value={draft.label} onChange={onChange('label')} required />
      <TextField
        id="tier-rank"
        label="Rank"
        type="number"
        value={draft.rank}
        onChange={onChange('rank')}
        required
      />
      <FormField id="tier-description" label="Description">
        <textarea
          id="tier-description"
          className="flex w-full rounded-md border border-border bg-background px-3 py-1.5 text-sm shadow-sm"
          value={draft.description}
          onChange={onChange('description')}
        />
      </FormField>
      <TextField
        id="tier-price"
        label="Price label"
        value={draft.priceLabel}
        onChange={onChange('priceLabel')}
      />
    </>
  )
}
```

- [ ] **Step 4: Swap the three error paragraphs**

- `TierFormDialog.tsx`: replace the `mutation.error ? <p …>` block with `<FormError error={mutation.error} />`; import `FormError` from `@/shared/ui`.
- `TierActions.tsx`: replace the `patch.error ? <p …>` block with `<FormError error={patch.error} />`.
- `TierDeactivate.tsx`: replace the `deactivate.error ? <span …>` block with `<FormError inline error={deactivate.error} />` — inline because the container is a `<span>` row.

- [ ] **Step 5: Run the regression net**

Run: `npm run test -- src/features/admin/components/policies`
Expected: PASS unchanged. If a test fails, STOP and report.

- [ ] **Step 6: Gate and commit**

Run: `npm run lint && npm run build && npm run test`

Commit message:

```
refactor: adopt shared form components across policy and tier forms

Also surfaces PolicyCard's mutation error, which was silently
swallowed — same defect class as the quota-form fix.
```

---

### Task 5: Adopt in catalog, settings and users files

**Files:**
- Modify: `catalog/DraftFields.tsx`, `catalog/PricingCells.tsx`, `catalog/ModelRow.tsx`, `catalog/ProviderSection.tsx`, `catalog/AddModelForm.tsx`, `settings/ValueEditor.tsx`, `settings/SettingRow.tsx`, `users/UserRowActions.tsx`
- Tests (regression net): `SettingsPage.test.tsx`, `UsersPage.test.tsx`

**Interfaces:**
- Consumes: `Input` (with `size="sm"`), `FormError` from `@/shared/ui`. These are the aria-label inline editors — they get NO visible label (spec §3).

- [ ] **Step 1: DraftFields** — drop the local `FIELD` constant; render `<Input size="sm" key={field.key} value={draft[field.key]} aria-label={field.label} placeholder={field.label} onChange={…} />` (import `Input` from `@/shared/ui`). Note the intended slight shrink: `text-sm` → `text-xs`.

- [ ] **Step 2: PricingCells** — drop `PRICE_INPUT`; both cells become `<Input size="sm" className="w-20" … />` with their existing `value`/`aria-label`/`onChange`; the error block becomes `<FormError error={patch.error} />`.

- [ ] **Step 3: ValueEditor** — the input becomes `<Input size="sm" className="w-48 font-mono" value={text} aria-label={`Value for ${setting.key}`} onChange={…} />`; the error block becomes `<FormError error={save.error} />`.

- [ ] **Step 4: Error-only swaps** — in each file replace the `x.error ? <p className="text-xs text-destructive">…` block with `FormError` (import from `@/shared/ui`):
  - `ModelRow.tsx`: `<FormError error={patch.error} />`
  - `ProviderSection.tsx`: `<FormError className="px-3 py-1" error={patch.error} />`
  - `AddModelForm.tsx`: `<FormError error={create.error} />`
  - `SettingRow.tsx`: `<FormError error={clear.error} />`
  - `UserRowActions.tsx`: `<FormError error={error} />`

- [ ] **Step 5: Run the regression net**

Run: `npm run test -- src/features/admin`
Expected: PASS unchanged.

- [ ] **Step 6: Gate and commit**

Run: `npm run lint && npm run build && npm run test`

Commit message:

```
refactor: adopt Input size=sm and FormError in catalog/settings/users

The three inline editors that each hand-rolled a compact input style
now share one variant; their aria-labels stay, no visible labels added.
```

---

### Task 6: Final verification

**Files:** none (verification only).

- [ ] **Step 1: Confirm no stragglers**

Run: `grep -rn "text-xs text-destructive" src/features/admin --include="*.tsx" | grep -v test`
Expected: no matches outside `shared/ui` — every admin error line goes through `FormError`. (Page-level `text-sm text-destructive` load-failure states remain; they are not form errors.)

Run: `grep -rn "border-border bg-background px-" src/features/admin --include="*.tsx"`
Expected: no hand-rolled input class strings remain in admin (the `TierDeactivate` `<select>` keeps its class — selects are out of scope).

- [ ] **Step 2: Full gates**

Run: `npm run lint && npm run build && npm run test`
Expected: all pass. Test count ≥ 159 (143 before + 16 shared-ui).

- [ ] **Step 3: Visual sanity check (manual)**

Confirm with the user before closing out: the Membership tiers page cards are taller (expected, ~40%), the catalog table and settings rows look unchanged apart from `DraftFields` being slightly smaller.
