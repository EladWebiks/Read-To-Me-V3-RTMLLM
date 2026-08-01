# Shared Select Components Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `Select` and `SelectField` to `shared/ui` as exact siblings of `Input` / `TextField`, and adopt them at all 13 hand-rolled `<select>` sites (10 files).

**Architecture:** `Select` is a styled native `<select>` with the same two size variants as `Input` (shadowing the native `size` attribute via `Omit`, exactly like `Input` does). `SelectField` composes the existing `FormField` + `describedBy` helper exactly as `TextField` does. Adoption replaces class strings only — no behaviour changes; existing tests are the regression net and a test that needs editing means stop and report.

**Tech Stack:** React 19, TypeScript strict, Tailwind v4, vitest + @testing-library/react.

**Spec:** `docs/superpowers/specs/2026-08-01-select-field-design.md`

## Global Constraints

- All frontend commands run from `frontend/` (`npm run lint`, `npm run build`, `npm run test`, `npx vitest run <file>`).
- ESLint hard limits: file ≤ 110 lines, function ≤ 60 lines, nesting ≤ 3 (barrels and test files exempt). Split instead of disabling rules.
- vitest runs with `globals: false` — import `describe/it/expect/afterEach` from `vitest`, and register `afterEach(cleanup)` (no auto-cleanup). No jest-dom: use plain matchers (`toBe`, `toContain`, `getAttribute`).
- Strict TS, no `any`. Native appearance is kept — no `appearance-none`, no custom chevron.
- Commits: write the message to a file, then `bash scripts/git-commit-clean.sh /tmp/msg.txt` from the repo root (`c:\Code\Read-To-Me-V3-RTMLLM`). **Never add any attribution trailer.** Verify with `git log -1 --format=%B`.
- `cn` (`@/shared/lib/cn`) uses tailwind-merge, so a call-site `w-auto` in `className` correctly overrides the variant's `w-full`.
- Adoption regression rule (spec §5): existing tests query by `aria-label` and displayed value and must pass **unchanged**. A test that needs editing is evidence of a behaviour change — stop and report it, don't rewrite it.

---

### Task 1: `Select` primitive

**Files:**
- Create: `frontend/src/shared/ui/select.tsx`
- Modify: `frontend/src/shared/ui/index.ts` (add export)
- Test: `frontend/src/shared/ui/form-field.test.tsx` (extend — it already covers the field family)

**Interfaces:**
- Consumes: `cn` from `@/shared/lib/cn`.
- Produces: `Select` — `(props: Omit<SelectHTMLAttributes<HTMLSelectElement>, 'size'> & { size?: 'default' | 'sm' }) => JSX.Element`. `default` = `h-9 w-full` standard control; `sm` = `h-7 text-xs` compact inline control (no `w-full`). Later tasks import it from `@/shared/ui`.

- [ ] **Step 1: Write the failing tests**

Append to `frontend/src/shared/ui/form-field.test.tsx` (add `Select` to the imports at the top: `import { Select } from './select'`):

```tsx
describe('Select size', () => {
  it('defaults to the standard h-9 style', () => {
    render(
      <Select aria-label="standard" value="a" onChange={() => {}}>
        <option value="a">A</option>
      </Select>,
    )
    const select = screen.getByLabelText('standard')
    expect(select.tagName).toBe('SELECT')
    expect(select.className).toContain('h-9')
    expect(select.className).toContain('w-full')
  })

  it('sm renders the compact inline style', () => {
    render(
      <Select size="sm" aria-label="compact" value="a" onChange={() => {}}>
        <option value="a">A</option>
      </Select>,
    )
    const className = screen.getByLabelText('compact').className
    expect(className).toContain('h-7')
    expect(className).toContain('text-xs')
    expect(className).not.toContain('w-full') // inline editors size themselves
  })

  it('forwards native select props', () => {
    render(
      <Select aria-label="native" name="tier" disabled required value="a" onChange={() => {}}>
        <option value="a">A</option>
      </Select>,
    )
    const select = screen.getByLabelText('native')
    expect(select.getAttribute('name')).toBe('tier')
    expect(select.hasAttribute('disabled')).toBe(true)
    expect(select.hasAttribute('required')).toBe(true)
  })
})
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `npx vitest run src/shared/ui/form-field.test.tsx` (from `frontend/`)
Expected: FAIL — cannot resolve `./select`.

- [ ] **Step 3: Write the implementation**

Create `frontend/src/shared/ui/select.tsx`:

```tsx
import type { SelectHTMLAttributes } from 'react'
import { cn } from '@/shared/lib/cn'

// Native <select size={n}> (visible row count) is shadowed by the variant
// name, exactly like Input. No call site uses it; the escape hatch is a raw
// <select>, not widening this type.
type Props = Omit<SelectHTMLAttributes<HTMLSelectElement>, 'size'> & {
  /** 'sm' is the compact inline-editor style (tables, filter bars). */
  size?: 'default' | 'sm'
}

const SIZES = {
  default:
    'h-9 w-full rounded-md border border-border bg-background px-3 py-1 text-sm shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50',
  sm: 'h-7 rounded border border-border bg-background px-1.5 py-0.5 text-xs focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50',
}

export function Select({ className, size = 'default', ...props }: Props) {
  return <select className={cn(SIZES[size], className)} {...props} />
}
```

(The size strings mirror `frontend/src/shared/ui/input.tsx:9-13` minus the input-only `flex` and `placeholder:` utilities, so a `Select` and an `Input` side by side line up.)

Add to `frontend/src/shared/ui/index.ts`, after the `Input` export:

```ts
export { Select } from './select'
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `npx vitest run src/shared/ui/form-field.test.tsx`
Expected: PASS (all, including the pre-existing Input/TextField/FormField tests).

- [ ] **Step 5: Lint and typecheck**

Run: `npm run lint && npm run build`
Expected: clean.

- [ ] **Step 6: Commit**

```bash
cat > /tmp/msg.txt <<'EOF'
feat: add shared Select primitive with Input-matched size variants
EOF
bash scripts/git-commit-clean.sh /tmp/msg.txt
git log -1 --format=%B
```

---

### Task 2: `SelectField`

**Files:**
- Create: `frontend/src/shared/ui/select-field.tsx`
- Modify: `frontend/src/shared/ui/index.ts` (add export)
- Test: `frontend/src/shared/ui/form-field.test.tsx` (extend)

**Interfaces:**
- Consumes: `Select` (Task 1), `FormField` (`./form-field`), `describedBy(id, hasHint, hasError)` (`./field-aria`).
- Produces: `SelectField` — `(props: Omit<SelectHTMLAttributes<HTMLSelectElement>, 'id' | 'size'> & { id: string; label: ReactNode; hint?: ReactNode; error?: string | Error | null; children: ReactNode }) => JSX.Element`. Options are passed as `children` (`<option>` elements) — there is deliberately no `options` array prop (spec §2.2).

- [ ] **Step 1: Write the failing tests**

Append to `frontend/src/shared/ui/form-field.test.tsx` (add `import { SelectField } from './select-field'`):

```tsx
describe('SelectField', () => {
  const options = (
    <>
      <option value="">Default</option>
      <option value="edge">Edge</option>
      <option value="sapi">SAPI</option>
    </>
  )

  it('associates the label with the select', () => {
    render(
      <SelectField id="v" label="Voice" value="edge" onChange={() => {}}>
        {options}
      </SelectField>,
    )
    expect(screen.getByLabelText('Voice').tagName).toBe('SELECT')
  })

  it('renders options and selects the current value', () => {
    render(
      <SelectField id="v" label="Voice" value="sapi" onChange={() => {}}>
        {options}
      </SelectField>,
    )
    const select = screen.getByLabelText('Voice') as HTMLSelectElement
    expect(screen.getAllByRole('option')).toHaveLength(3)
    expect(select.value).toBe('sapi')
  })

  it('wires an error to aria-invalid, aria-describedby and an alert', () => {
    render(
      <SelectField id="v" label="Voice" error="Bad" value="" onChange={() => {}}>
        {options}
      </SelectField>,
    )
    const select = screen.getByLabelText('Voice')
    expect(select.getAttribute('aria-invalid')).toBe('true')
    expect(select.getAttribute('aria-describedby')).toBe('v-error')
    expect(screen.getByRole('alert').id).toBe('v-error')
  })

  it('lists hint and error ids in aria-describedby, hint first', () => {
    render(
      <SelectField id="v" label="Voice" hint="H" error="E" value="" onChange={() => {}}>
        {options}
      </SelectField>,
    )
    expect(screen.getByLabelText('Voice').getAttribute('aria-describedby')).toBe(
      'v-hint v-error',
    )
    expect(document.getElementById('v-hint')?.textContent).toBe('H')
  })

  it('adds no aria noise when healthy', () => {
    render(
      <SelectField id="v" label="Voice" value="" onChange={() => {}}>
        {options}
      </SelectField>,
    )
    const select = screen.getByLabelText('Voice')
    expect(select.getAttribute('aria-invalid')).toBeNull()
    expect(select.getAttribute('aria-describedby')).toBeNull()
    expect(screen.queryByRole('alert')).toBeNull()
  })

  it('forwards native select props', () => {
    render(
      <SelectField id="v" label="Voice" name="voice" disabled value="" onChange={() => {}}>
        {options}
      </SelectField>,
    )
    const select = screen.getByLabelText('Voice')
    expect(select.getAttribute('name')).toBe('voice')
    expect(select.hasAttribute('disabled')).toBe(true)
  })
})
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `npx vitest run src/shared/ui/form-field.test.tsx`
Expected: FAIL — cannot resolve `./select-field`.

- [ ] **Step 3: Write the implementation**

Create `frontend/src/shared/ui/select-field.tsx` (mirror of `text-field.tsx`):

```tsx
import type { ReactNode, SelectHTMLAttributes } from 'react'
import { describedBy } from './field-aria'
import { FormField } from './form-field'
import { Select } from './select'

type Props = Omit<SelectHTMLAttributes<HTMLSelectElement>, 'id' | 'size'> & {
  id: string
  label: ReactNode
  hint?: ReactNode
  error?: string | Error | null
  /** <option> elements — call sites disagree on option shape, so no mapping prop. */
  children: ReactNode
}

/** Label + Select + hint + error as one unit, with the ARIA wiring done. */
export function SelectField({ id, label, hint, error, children, ...props }: Props) {
  const hasError = error != null && error !== ''
  return (
    <FormField id={id} label={label} hint={hint} error={error}>
      <Select
        {...props}
        id={id}
        aria-invalid={hasError ? true : undefined}
        aria-describedby={describedBy(id, hint != null, hasError)}
      >
        {children}
      </Select>
    </FormField>
  )
}
```

Add to `frontend/src/shared/ui/index.ts`, next to the `TextField` export:

```ts
export { SelectField } from './select-field'
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `npx vitest run src/shared/ui/form-field.test.tsx`
Expected: PASS.

- [ ] **Step 5: Lint and typecheck**

Run: `npm run lint && npm run build`
Expected: clean.

- [ ] **Step 6: Commit**

```bash
cat > /tmp/msg.txt <<'EOF'
feat: add shared SelectField composing FormField with ARIA wiring
EOF
bash scripts/git-commit-clean.sh /tmp/msg.txt
git log -1 --format=%B
```

---

### Task 3: Adopt `Select size="sm"` on the three admin selects

This closes the gap called out in spec §1: `TierDeactivate`, `UserRow`, `ToolCallFilters` are the reason the "no hand-rolled control styles in admin" check could not come back clean.

**Files:**
- Modify: `frontend/src/features/admin/components/policies/TierDeactivate.tsx:31-42`
- Modify: `frontend/src/features/admin/components/users/UserRow.tsx:24-38`
- Modify: `frontend/src/features/admin/components/toolcalls/ToolCallFilters.tsx:28-40`
- Test (regression, unchanged): `frontend/src/features/admin/components/policies/TierDeactivate.test.tsx`, `frontend/src/features/admin/components/users/UsersPage.test.tsx`

**Interfaces:**
- Consumes: `Select` from `@/shared/ui` (Task 1).
- Produces: no interface changes — props of all three components are untouched.

- [ ] **Step 1: Convert TierDeactivate**

In `TierDeactivate.tsx`, change the import line 4 to `import { FormError, Select } from '@/shared/ui'` and replace the `<select …>…</select>` block (lines 31–42) with:

```tsx
      <Select
        size="sm"
        aria-label={`Migrate ${tier.label} users to`}
        value={value}
        onChange={(event) => setTarget(event.target.value)}
      >
        {others.map((t) => (
          <option key={t.slug} value={t.slug}>
            {t.label}
          </option>
        ))}
      </Select>
```

- [ ] **Step 2: Convert UserRow's MembershipSelect**

In `UserRow.tsx`, add `import { Select } from '@/shared/ui'` and replace the `<select …>…</select>` in `MembershipSelect` (lines 24–37) with:

```tsx
    <Select
      size="sm"
      value={user.membership}
      aria-label={`Membership for ${user.username} (operator override)`}
      onChange={(event) =>
        patch.mutate({ id: user.id, body: { membership: event.target.value } })
      }
    >
      {options.map((tier) => (
        <option key={tier.slug} value={tier.slug}>
          {tier.label}
        </option>
      ))}
    </Select>
```

- [ ] **Step 3: Convert the ToolCallFilters select**

In `ToolCallFilters.tsx`, add `import { Select } from '@/shared/ui'` and replace only the `<select …>…</select>` (lines 28–40) with:

```tsx
      <Select
        size="sm"
        aria-label="Filter by risk level"
        value={filters.risk_level ?? ''}
        onChange={(event) => onChange({ ...filters, risk_level: event.target.value })}
      >
        <option value="">Any risk</option>
        {RISK_LEVELS.map((risk) => (
          <option key={risk} value={risk}>
            {risk}
          </option>
        ))}
      </Select>
```

The two `<input>`s and the `FIELD` const stay exactly as they are — inputs are a separate adoption gap, out of scope here (spec §1).

- [ ] **Step 4: Run the regression tests unchanged**

Run: `npx vitest run src/features/admin`
Expected: PASS with **zero test edits**. They query by `aria-label` and option text, both preserved. If any fails, stop and report — that is a behaviour change, not a test to fix.

- [ ] **Step 5: Lint and typecheck**

Run: `npm run lint && npm run build`
Expected: clean.

- [ ] **Step 6: Commit**

```bash
cat > /tmp/msg.txt <<'EOF'
refactor: adopt shared Select on the three admin selects
EOF
bash scripts/git-commit-clean.sh /tmp/msg.txt
git log -1 --format=%B
```

---

### Task 4: Adopt `SelectField` in the audio download modal

The two stacked label+select controls (`ChapterSelect`, `VoiceSelect`) become `SelectField`s. They are rendered from `AudioModalFields`, which must now supply `id`s (SelectField requires one for the label association).

**Files:**
- Modify: `frontend/src/features/downloads/components/audio-modal/AudioModalSelects.tsx`
- Modify: `frontend/src/features/downloads/components/audio-modal/AudioModalFields.tsx:22-47`

**Interfaces:**
- Consumes: `SelectField` from `@/shared/ui` (Task 2).
- Produces: `ChapterSelect` and `VoiceSelect` each gain a **required** `id: string` prop (breaking for their only caller, `AudioModalFields`, updated in the same task). `ProviderToggle` is untouched.

- [ ] **Step 1: Convert ChapterSelect and VoiceSelect**

Replace `ChapterSelect` (lines 5–35) and `VoiceSelect` (lines 67–95) in `AudioModalSelects.tsx`; add `import { SelectField } from '@/shared/ui'` at the top. `ProviderToggle` stays as is.

```tsx
export function ChapterSelect({
  id,
  label,
  value,
  options,
  disabled,
  onChange,
}: {
  id: string
  label: string
  value: number
  options: ChapterSummary[]
  disabled: boolean
  onChange: (value: number) => void
}) {
  return (
    <SelectField
      id={id}
      label={label}
      value={value}
      disabled={disabled}
      onChange={(event) => onChange(Number(event.target.value))}
    >
      {options.map((ch) => (
        <option key={ch.id} value={ch.chapter_number}>
          {ch.chapter_number}. {ch.title || 'Untitled'}
        </option>
      ))}
    </SelectField>
  )
}
```

```tsx
export function VoiceSelect({
  id,
  value,
  voices,
  disabled,
  onChange,
}: {
  id: string
  value: string
  voices: ServerVoice[]
  disabled: boolean
  onChange: (value: string) => void
}) {
  return (
    <SelectField
      id={id}
      label="Voice"
      value={value}
      disabled={disabled}
      onChange={(event) => onChange(event.target.value)}
    >
      {voices.map((voice) => (
        <option key={voice.id} value={voice.id}>
          {voice.name}
        </option>
      ))}
    </SelectField>
  )
}
```

- [ ] **Step 2: Pass ids from AudioModalFields**

In `AudioModalFields.tsx`, add the `id` prop at the three call sites:

- first `ChapterSelect` (line 22): add `id="download-from-chapter"`
- second `ChapterSelect` (line 29): add `id="download-to-chapter"`
- `VoiceSelect` (line 42): add `id="download-voice"`

- [ ] **Step 3: Verify**

Run: `npm run lint && npm run build && npm run test`
Expected: all clean/green. (There are no dedicated tests for this modal; `tsc -b` is the guard for the new required `id` prop — it will flag any missed caller.)

Expected visual deltas (spec §4, accepted): the label gains `font-medium`, and the selects go to the standard full-width `h-9`.

- [ ] **Step 4: Commit**

```bash
cat > /tmp/msg.txt <<'EOF'
refactor: adopt SelectField in the audio download modal
EOF
bash scripts/git-commit-clean.sh /tmp/msg.txt
git log -1 --format=%B
```

---

### Task 5: Adopt `Select` at the inline-label reader/download sites

These keep their wrapping `<label className="flex items-center gap-1">` (implicit association already works; converting the layout is out of scope — spec §3.1). Because they sit in horizontal player-bar rows, each passes `w-auto` so the variant's `w-full` doesn't inflate the row (`cn` is tailwind-merge, so the override wins).

**Files:**
- Modify: `frontend/src/features/reader/components/player/PlayerControls.tsx:13-20`
- Modify: `frontend/src/features/reader/components/player/VoicePickers.tsx` (3 selects)
- Modify: `frontend/src/features/downloads/components/download-form/DownloadFields.tsx:13-20`
- Modify: `frontend/src/features/reader/components/ReaderBottomBar.tsx:26-37`

**Interfaces:**
- Consumes: `Select` from `@/shared/ui`.
- Produces: no prop changes anywhere.

- [ ] **Step 1: PlayerControls engine select**

Add `import { Select } from '@/shared/ui'`; replace the `<select …>` (lines 13–20) with:

```tsx
        <Select
          className="w-auto"
          value={props.engine}
          onChange={(event) => props.onEngine(event.target.value as PlaybackEngine)}
        >
          <option value="browser">Browser</option>
          <option value="server">Server</option>
        </Select>
```

- [ ] **Step 2: VoicePickers (3 selects)**

Add `import { Select } from '@/shared/ui'`. Provider select (lines 10–17) → `<Select className="w-auto" …>` with the same value/onChange/options. Both voice selects (lines 21–32 and 40–51) → `<Select className="w-auto max-w-48" …>` keeping their `value`, `onChange` and options exactly as today (including the `<option value="">Default</option>` placeholder).

Example — the server-voice select:

```tsx
          <Select
            className="w-auto max-w-48"
            value={props.serverVoice ?? ''}
            onChange={(event) => props.onServerVoice(event.target.value || null)}
          >
            <option value="">Default</option>
            {props.serverVoices.map((voice) => (
              <option key={voice.id} value={voice.id}>
                {voice.name}
              </option>
            ))}
          </Select>
```

And the browser-voice select:

```tsx
      <Select
        className="w-auto max-w-48"
        value={props.voiceURI ?? ''}
        onChange={(event) => props.onVoice(event.target.value || null)}
      >
        <option value="">Default</option>
        {props.browserVoices.map((voice) => (
          <option key={voice.voiceURI} value={voice.voiceURI}>
            {voice.name}
          </option>
        ))}
      </Select>
```

- [ ] **Step 3: DownloadFields provider select**

Add `import { Select } from '@/shared/ui'`; replace the `<select …>` in `ProviderSelect` (lines 13–20) with:

```tsx
      <Select
        className="w-auto"
        value={value}
        onChange={(event) => onChange(event.target.value as DownloadProvider)}
      >
        <option value="edge">Edge</option>
        <option value="sapi">SAPI</option>
      </Select>
```

`NumField` (an `<input>`) is untouched.

- [ ] **Step 4: ReaderBottomBar chapter select**

Change the import at line 2 to `import { Button, Select } from '@/shared/ui'`; replace the `<select …>` (lines 26–37) with:

```tsx
      <Select
        className="min-w-[12rem] flex-1"
        value={props.chapterId}
        aria-label="Chapter list"
        onChange={(event) => props.onNavigate(event.target.value)}
      >
        {props.chapters.map((chapter) => (
          <option key={chapter.id} value={chapter.id}>
            {chapter.chapter_number}. {chapter.title || 'Untitled'}
          </option>
        ))}
      </Select>
```

No `w-auto` needed here: `flex-1` sets `flex-basis: 0%`, which controls the main size regardless of `w-full`. This drops the dead `border-input` class (not a token this app defines — spec §1.1) as a side effect.

- [ ] **Step 5: Verify**

Run: `npm run lint && npm run build && npm run test`
Expected: clean/green with zero test edits (reader/download suites query by `aria-label` and display value).

**Manual visual check (spec §4 — "the one to check before merging"):** run the app, open the reader — the player bar gets slightly taller (`py-1` → `h-9`). If the height matters, the fix is `size="sm"` at those sites, not a third variant. Record the observation in the task notes for the human reviewer.

- [ ] **Step 6: Commit**

```bash
cat > /tmp/msg.txt <<'EOF'
refactor: adopt shared Select in reader player, bottom bar and download form
EOF
bash scripts/git-commit-clean.sh /tmp/msg.txt
git log -1 --format=%B
```

---

### Task 6: Adopt `Select` in the assistant confirmation panel

**Files:**
- Modify: `frontend/src/features/assistant/components/ConfirmationFields.tsx:62-75`
- Modify: `frontend/src/features/assistant/components/ConfirmationVoiceControl.tsx:16-31`

**Interfaces:**
- Consumes: `Select` from `@/shared/ui`.
- Produces: no prop changes.

- [ ] **Step 1: ConfirmationFields options select**

Add `import { Select } from '@/shared/ui'`; in `FieldControl`, replace the `<select …>` (lines 62–75) with:

```tsx
      <Select
        disabled={props.busy}
        value={stringValue(props.values[props.field.name])}
        onChange={(event) => props.onChange(props.field.name, event.target.value)}
      >
        {props.field.options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </Select>
```

(The default variant already includes `w-full`, so no className is needed. The text `<input>` below it is out of scope.) Note: inside the `if (props.field.options?.length)` guard, keep `props.field.options.map` exactly as today — TS narrows the optional through the guard.

- [ ] **Step 2: ConfirmationVoiceControl**

Add `import { Select } from '@/shared/ui'`; replace the `<select …>` (lines 16–31) with:

```tsx
    <Select
      disabled={props.busy || voices.isLoading}
      value={stringValue(props.values.voice)}
      onChange={(event) => props.onChange(props.field.name, event.target.value || null)}
    >
      <option value="">Provider default</option>
      {(voices.data ?? []).map((voice) => (
        <option key={voice.id} value={voice.id}>
          {voice.name}
          {voice.locale ? ` (${voice.locale})` : ''}
        </option>
      ))}
    </Select>
```

Expected visual delta (spec §4, accepted): `rounded-lg` → `rounded-md`, matching every other control in the assistant panel.

- [ ] **Step 3: Verify**

Run: `npm run lint && npm run build && npm run test`
Expected: clean/green.

- [ ] **Step 4: Commit**

```bash
cat > /tmp/msg.txt <<'EOF'
refactor: adopt shared Select in assistant confirmation controls
EOF
bash scripts/git-commit-clean.sh /tmp/msg.txt
git log -1 --format=%B
```

---

### Task 7: Completion sweep

**Files:** none created — verification only.

- [ ] **Step 1: Confirm no hand-rolled selects remain**

Run from `frontend/`: `grep -rn "<select" src/`
Expected: exactly one hit — `src/shared/ui/select.tsx` (the primitive itself). Any other hit is a missed site; convert it using the matching pattern from Tasks 3–6 (spec §3 lists all ten files) and re-run.

- [ ] **Step 2: Confirm the dead token is gone**

Run: `grep -rn "border-input" src/`
Expected: no hits.

- [ ] **Step 3: Full quality gates**

Run: `npm run lint && npm run build && npm run test`
Expected: all clean/green.

- [ ] **Step 4: Commit (only if the sweep changed anything)**

If Steps 1–2 required fixes, commit them:

```bash
cat > /tmp/msg.txt <<'EOF'
refactor: convert stragglers found in select adoption sweep
EOF
bash scripts/git-commit-clean.sh /tmp/msg.txt
git log -1 --format=%B
```
