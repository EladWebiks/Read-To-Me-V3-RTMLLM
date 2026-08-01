# Query State & Loaders Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the 13 hand-written loading/error early-returns with one `QueryState` wrapper and a family of shape-matched loaders (`Skeleton`, `SkeletonText`, `SkeletonTable`, `SkeletonCards`, `SkeletonRows`, `Spinner`, `InlineLoader`), adding a 160ms anti-flicker delay, Retry-on-error, and `role="status"`/`role="alert"` accessibility.

**Architecture:** Pure presentational loaders in `shared/ui` (the only stateful logic — the delay timer — lives in `query-state.tsx`). `QueryState` takes plain booleans, not a react-query result object, so `shared/ui` keeps importing nothing but React, `cn`, Radix and lucide. Adoption keeps each page's static chrome (headings, filter bars) rendered and wraps only the async region; the loading/error/empty branches render inside a status/alert wrapper while settled children render bare (no wrapper div) so flex/grid layouts are untouched.

**Tech Stack:** React 19, TypeScript strict, Tailwind v4 + CSS variables in `index.css`, lucide-react, vitest + @testing-library/react (fake timers for the delay).

**Spec:** `docs/superpowers/specs/2026-08-01-query-state-design.md`

## Global Constraints

- All frontend commands run from `frontend/` (`npm run lint`, `npm run build`, `npm run test`, `npx vitest run <file>`).
- ESLint hard limits: file ≤ 110 lines, function ≤ 60 lines, nesting ≤ 3 (barrels and test files exempt). Split components instead of disabling rules.
- vitest runs with `globals: false` — import from `vitest`, register `afterEach(cleanup)`. No jest-dom — plain matchers only.
- **No `dark:` variants anywhere** — the skeleton tint derives from `--muted-foreground` via `color-mix`, correct in both themes (spec §2).
- Never call a state setter inside `useEffect` to derive/sync state — the delay hook uses a timer effect (external side effect) plus React's render-time-adjustment pattern for the reset.
- Error copy is normalised to **"Couldn't load X."** at every adoption site. sr-only loading labels use "Loading X…".
- The shimmer is **1.6s** (calm, in the app's 1.8–2.4s ambient range); the delay default is **160ms**; reduced motion kills the shimmer but **keeps the spinner spinning** (it's the only signal, spec §3.2).
- `QueryState` deliberately does **not** animate children in (spec §4.4) — pages already run `.animate-fade-in-up` / motion staggers; only the loader fades in.
- Adoption regression rule (spec §6): existing tests assert on loaded content and must pass unchanged. A test asserting the literal old copy must be **called out and reported**, not silently rewritten.
- Commits: write the message to a file, then `bash scripts/git-commit-clean.sh /tmp/msg.txt` from the repo root. **Never add any attribution trailer.** Verify with `git log -1 --format=%B`.
- Out of scope (spec §8): Suspense, `isFetching` refresh indicators, progress bars, toasts. Auth guards, reader pages, `ChapterEditorPage`, `ReaderHubPage`, `ResumeReadingPage` and `UsageSummaryTiles` also have loading paragraphs but are **not** in the spec's inventory — leave them alone.

---

### Task 1: Skeleton CSS + `Skeleton` + `SkeletonText`

**Files:**
- Modify: `frontend/src/index.css` (keyframes + `.rtm-skeleton` after the `.animate-fade-in-up` block ~line 145; reduced-motion entry inside the existing `@media (prefers-reduced-motion: reduce)` block at lines 306–320)
- Create: `frontend/src/shared/ui/skeleton.tsx`
- Modify: `frontend/src/shared/ui/index.ts`
- Test: create `frontend/src/shared/ui/skeleton.test.tsx`

**Interfaces:**
- Consumes: `cn` from `@/shared/lib/cn`; the `.rtm-skeleton` CSS class.
- Produces: `Skeleton` — `({ className }: { className?: string }) => JSX.Element`, an `aria-hidden` tinted block whose shape comes entirely from `className`. `SkeletonText` — `({ lines = 3 }: { lines?: number })`. Task 3's layouts build on `Skeleton`.

- [ ] **Step 1: Write the failing tests**

Create `frontend/src/shared/ui/skeleton.test.tsx`:

```tsx
import { cleanup, render } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'
import { Skeleton, SkeletonText } from './skeleton'

// vitest runs with globals:false, so testing-library's auto-cleanup is not registered.
afterEach(cleanup)

describe('Skeleton', () => {
  it('merges className onto the rtm-skeleton base', () => {
    const { container } = render(<Skeleton className="h-4 w-32" />)
    const block = container.firstElementChild as HTMLElement
    expect(block.className).toContain('rtm-skeleton')
    expect(block.className).toContain('h-4')
    expect(block.className).toContain('w-32')
  })

  it('is aria-hidden so it never reaches the accessibility tree', () => {
    const { container } = render(<Skeleton className="h-4" />)
    expect(container.firstElementChild?.getAttribute('aria-hidden')).toBe('true')
  })
})

describe('SkeletonText', () => {
  it('renders the requested number of bars, last one narrower', () => {
    const { container } = render(<SkeletonText lines={3} />)
    const bars = container.querySelectorAll('.rtm-skeleton')
    expect(bars).toHaveLength(3)
    expect(bars[2].className).toContain('w-3/5')
    expect(bars[0].className).toContain('w-full')
  })

  it('is aria-hidden at the wrapper', () => {
    const { container } = render(<SkeletonText />)
    expect(container.firstElementChild?.getAttribute('aria-hidden')).toBe('true')
  })
})
```

(If the `allHidden` helper's `:has` selector proves flaky under jsdom, drop the helper and keep the direct `getAttribute('aria-hidden')` assertions — they are the real contract.)

- [ ] **Step 2: Run tests to verify they fail**

Run: `npx vitest run src/shared/ui/skeleton.test.tsx`
Expected: FAIL — cannot resolve `./skeleton`.

- [ ] **Step 3: Add the CSS**

In `frontend/src/index.css`, insert directly after the `.animate-fade-in-up` rule (line 145):

```css
@keyframes rtm-skeleton-sweep {
  from {
    background-position: -200% 0;
  }
  to {
    background-position: 200% 0;
  }
}

/* Loading stand-in blocks. Tint derives from --muted-foreground (14%, the
   inline-code tint), so it is correct in both themes with no dark: variant.
   1.6s sits in the app's calm ambient range (assistant-pulse is 2.2s). */
.rtm-skeleton {
  background-color: color-mix(in srgb, var(--muted-foreground) 14%, transparent);
  background-image: linear-gradient(
    90deg,
    transparent 0%,
    color-mix(in srgb, var(--muted-foreground) 12%, transparent) 50%,
    transparent 100%
  );
  background-size: 200% 100%;
  animation: rtm-skeleton-sweep 1.6s ease-in-out infinite;
}
```

And inside the existing `@media (prefers-reduced-motion: reduce)` block (after the `.assistant-stream-caret` rule), add:

```css
  /* Degrade to the flat tint — no sweep. The Spinner intentionally keeps
     spinning under reduced motion; it is the only signal during a wait. */
  .rtm-skeleton {
    animation: none;
    background-image: none;
  }
```

- [ ] **Step 4: Write the components**

Create `frontend/src/shared/ui/skeleton.tsx`:

```tsx
import { cn } from '@/shared/lib/cn'

/** Tinted loading block; all shape comes from className, so it composes into anything. */
export function Skeleton({ className }: { className?: string }) {
  return <div aria-hidden="true" className={cn('rtm-skeleton rounded-md', className)} />
}

/** Stacked prose-shaped bars; the last is 60% width so it reads as text, not a block. */
export function SkeletonText({ lines = 3 }: { lines?: number }) {
  return (
    <div aria-hidden="true" className="space-y-2">
      {Array.from({ length: lines }, (_, index) => (
        <Skeleton
          key={index}
          className={index === lines - 1 ? 'h-4 w-3/5' : 'h-4 w-full'}
        />
      ))}
    </div>
  )
}
```

Add to `frontend/src/shared/ui/index.ts`:

```ts
export { Skeleton, SkeletonText } from './skeleton'
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `npx vitest run src/shared/ui/skeleton.test.tsx`
Expected: PASS.

- [ ] **Step 6: Lint and typecheck**

Run: `npm run lint && npm run build`
Expected: clean.

- [ ] **Step 7: Commit**

```bash
cat > /tmp/msg.txt <<'EOF'
feat: add Skeleton primitive with theme-derived shimmer
EOF
bash scripts/git-commit-clean.sh /tmp/msg.txt
git log -1 --format=%B
```

---

### Task 2: `Spinner` + `InlineLoader`

**Files:**
- Create: `frontend/src/shared/ui/spinner.tsx`
- Modify: `frontend/src/shared/ui/index.ts`
- Test: `frontend/src/shared/ui/skeleton.test.tsx` (extend)

**Interfaces:**
- Consumes: `LoaderCircle` from `lucide-react`, `cn`.
- Produces: `Spinner` — `({ size = 'md', className }: { size?: 'sm' | 'md'; className?: string })`, `aria-hidden`, always `animate-spin`. `InlineLoader` — `({ label }: { label: string })`, spinner + muted visible label on one line. This standardises the `LoaderCircle` + `animate-spin` idiom that `LiveStatusLine` already uses (spec §2).

- [ ] **Step 1: Write the failing tests**

Append to `frontend/src/shared/ui/skeleton.test.tsx` (add `import { InlineLoader, Spinner } from './spinner'`, and add `screen` to the `@testing-library/react` import — this task is its first use):

```tsx
describe('Spinner', () => {
  it('spins and stays out of the accessibility tree', () => {
    const { container } = render(<Spinner />)
    const icon = container.firstElementChild as HTMLElement
    expect(icon.getAttribute('aria-hidden')).toBe('true')
    expect(icon.getAttribute('class') ?? '').toContain('animate-spin')
  })

  it('sm renders the compact size', () => {
    const { container } = render(<Spinner size="sm" />)
    expect((container.firstElementChild as HTMLElement).getAttribute('class')).toContain(
      'size-3.5',
    )
  })
})

describe('InlineLoader', () => {
  it('renders its label as visible text next to a hidden spinner', () => {
    render(<InlineLoader label="Loading chapters…" />)
    expect(screen.getByText('Loading chapters…')).toBeTruthy()
  })
})
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `npx vitest run src/shared/ui/skeleton.test.tsx`
Expected: FAIL — cannot resolve `./spinner`.

- [ ] **Step 3: Write the implementation**

Create `frontend/src/shared/ui/spinner.tsx`:

```tsx
import { LoaderCircle } from 'lucide-react'
import { cn } from '@/shared/lib/cn'

const SIZES = { sm: 'size-3.5', md: 'size-5' }

/** The app's one spinner (the LiveStatusLine idiom, standardised). It keeps
 * spinning under reduced motion: it is the only signal that anything is
 * happening, and a small rotating icon is far less provocative than a
 * sweeping gradient — the skeleton shimmer is what gets disabled. */
export function Spinner({
  size = 'md',
  className,
}: {
  size?: 'sm' | 'md'
  className?: string
}) {
  return (
    <LoaderCircle aria-hidden="true" className={cn('animate-spin', SIZES[size], className)} />
  )
}

/** Spinner + muted label for small areas inside an already-rendered container,
 * where a skeleton would be more furniture than the content it stands in for. */
export function InlineLoader({ label }: { label: string }) {
  return (
    <span className="flex items-center gap-2 text-sm text-muted-foreground">
      <Spinner size="sm" />
      {label}
    </span>
  )
}
```

Add to `frontend/src/shared/ui/index.ts`:

```ts
export { InlineLoader, Spinner } from './spinner'
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `npx vitest run src/shared/ui/skeleton.test.tsx`
Expected: PASS.

- [ ] **Step 5: Lint, typecheck, commit**

Run: `npm run lint && npm run build`, then:

```bash
cat > /tmp/msg.txt <<'EOF'
feat: add Spinner and InlineLoader standardising the LoaderCircle idiom
EOF
bash scripts/git-commit-clean.sh /tmp/msg.txt
git log -1 --format=%B
```

---

### Task 3: `SkeletonTable`, `SkeletonCards`, `SkeletonRows`

**Files:**
- Create: `frontend/src/shared/ui/skeleton-layouts.tsx`
- Modify: `frontend/src/shared/ui/index.ts`
- Test: `frontend/src/shared/ui/skeleton.test.tsx` (extend)

**Interfaces:**
- Consumes: `Skeleton` (Task 1).
- Produces: `SkeletonTable({ rows = 8, cols = 5 })`, `SkeletonCards({ count = 6 })`, `SkeletonRows({ count = 3, height = 'h-12' })` — all `aria-hidden` at the wrapper. Adoption tasks 5–8 pass these to `QueryState`'s `loading` slot.

- [ ] **Step 1: Write the failing tests**

Append to `frontend/src/shared/ui/skeleton.test.tsx` (add `import { SkeletonCards, SkeletonRows, SkeletonTable } from './skeleton-layouts'`):

```tsx
describe('SkeletonTable', () => {
  it('renders one header bar plus rows, each with the requested cell count', () => {
    const { container } = render(<SkeletonTable rows={4} cols={3} />)
    // (1 header row + 4 body rows) × 3 cells
    expect(container.querySelectorAll('.rtm-skeleton')).toHaveLength(15)
    expect(container.firstElementChild?.getAttribute('aria-hidden')).toBe('true')
  })
})

describe('SkeletonCards', () => {
  it('renders the requested number of cards inside the library grid shape', () => {
    const { container } = render(<SkeletonCards count={6} />)
    expect(container.querySelectorAll('.rtm-skeleton')).toHaveLength(6)
    expect(container.firstElementChild?.className).toContain('sm:grid-cols-2')
    expect(container.firstElementChild?.getAttribute('aria-hidden')).toBe('true')
  })
})

describe('SkeletonRows', () => {
  it('renders count blocks at the requested height', () => {
    const { container } = render(<SkeletonRows count={3} height="h-10" />)
    const rows = container.querySelectorAll('.rtm-skeleton')
    expect(rows).toHaveLength(3)
    expect(rows[0].className).toContain('h-10')
  })
})
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `npx vitest run src/shared/ui/skeleton.test.tsx`
Expected: FAIL — cannot resolve `./skeleton-layouts`.

- [ ] **Step 3: Write the implementation**

Create `frontend/src/shared/ui/skeleton-layouts.tsx`:

```tsx
import { Skeleton } from './skeleton'

/** Mirrors the admin tables' border rhythm and px-3 py-1.5 cell metrics so the
 * swap to real rows does not shift layout. */
export function SkeletonTable({ rows = 8, cols = 5 }: { rows?: number; cols?: number }) {
  return (
    <div aria-hidden="true" className="w-full">
      {Array.from({ length: rows + 1 }, (_, row) => (
        <div
          key={row}
          className={
            row === 0 ? 'flex gap-3 px-3 py-1.5' : 'flex gap-3 border-t border-border/50 px-3 py-1.5'
          }
        >
          {Array.from({ length: cols }, (_, col) => (
            <Skeleton key={col} className="h-4 flex-1" />
          ))}
        </div>
      ))}
    </div>
  )
}

/** Mirrors LibraryGrid's exact grid so the card grid does not resize when real
 * books land. Count should be the page size. */
export function SkeletonCards({ count = 6 }: { count?: number }) {
  return (
    <div
      aria-hidden="true"
      className="grid auto-rows-40 grid-cols-1 gap-x-4 gap-y-4 pt-1 sm:grid-cols-2 xl:grid-cols-3"
    >
      {Array.from({ length: count }, (_, index) => (
        <Skeleton key={index} className="h-full rounded-lg" />
      ))}
    </div>
  )
}

/** Stacked full-width blocks for meter rows and file lists. */
export function SkeletonRows({
  count = 3,
  height = 'h-12',
}: {
  count?: number
  height?: string
}) {
  return (
    <div aria-hidden="true" className="space-y-2">
      {Array.from({ length: count }, (_, index) => (
        <Skeleton key={index} className={height} />
      ))}
    </div>
  )
}
```

Add to `frontend/src/shared/ui/index.ts`:

```ts
export { SkeletonCards, SkeletonRows, SkeletonTable } from './skeleton-layouts'
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `npx vitest run src/shared/ui/skeleton.test.tsx`
Expected: PASS.

- [ ] **Step 5: Lint, typecheck, commit**

Run: `npm run lint && npm run build`, then:

```bash
cat > /tmp/msg.txt <<'EOF'
feat: add table, card-grid and row skeleton layouts
EOF
bash scripts/git-commit-clean.sh /tmp/msg.txt
git log -1 --format=%B
```

---

### Task 4: `QueryState`

**Files:**
- Create: `frontend/src/shared/ui/query-state.tsx`
- Modify: `frontend/src/shared/ui/index.ts`
- Test: create `frontend/src/shared/ui/query-state.test.tsx`

**Interfaces:**
- Consumes: `Button` (`./button`, `variant="outline" size="sm"`).
- Produces:

```tsx
type Props = {
  isPending: boolean
  isError?: boolean
  isEmpty?: boolean
  loading: ReactNode          // a loader from Tasks 1–3
  errorLabel: string          // "Couldn't load X."
  emptyLabel?: ReactNode
  onRetry?: () => void
  label?: string              // sr-only, defaults to 'Loading…'
  delayMs?: number            // defaults to 160
  children: ReactNode
}
export function QueryState(props: Props): JSX.Element
```

Precedence: error → pending → empty → children. Settled children render **bare** (fragment, no wrapper div) so flex/grid parents are untouched. Plain booleans in — never a react-query result object.

- [ ] **Step 1: Write the failing tests**

Create `frontend/src/shared/ui/query-state.test.tsx`:

```tsx
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { QueryState } from './query-state'

afterEach(cleanup)

const base = {
  isPending: false,
  loading: <div data-testid="loader" />,
  errorLabel: "Couldn't load things.",
}

describe('QueryState', () => {
  it('renders children when not pending and not errored', () => {
    render(<QueryState {...base}>content</QueryState>)
    expect(screen.getByText('content')).toBeTruthy()
    expect(screen.queryByRole('status')).toBeNull()
  })

  it('renders error with role=alert, the label, and a Retry that calls onRetry', () => {
    const onRetry = vi.fn()
    render(
      <QueryState {...base} isError onRetry={onRetry}>
        content
      </QueryState>,
    )
    expect(screen.getByRole('alert').textContent).toContain("Couldn't load things.")
    expect(screen.queryByText('content')).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: 'Retry' }))
    expect(onRetry).toHaveBeenCalledTimes(1)
  })

  it('renders no Retry button when onRetry is omitted', () => {
    render(
      <QueryState {...base} isError>
        content
      </QueryState>,
    )
    expect(screen.queryByRole('button')).toBeNull()
  })

  it('error takes precedence over pending', () => {
    render(
      <QueryState {...base} isPending isError>
        content
      </QueryState>,
    )
    expect(screen.getByRole('alert')).toBeTruthy()
    expect(screen.queryByRole('status')).toBeNull()
  })

  it('isEmpty renders emptyLabel, and children win when not empty', () => {
    const { rerender } = render(
      <QueryState {...base} isEmpty emptyLabel={<p>Nothing yet.</p>}>
        content
      </QueryState>,
    )
    expect(screen.getByText('Nothing yet.')).toBeTruthy()
    expect(screen.queryByText('content')).toBeNull()
    rerender(
      <QueryState {...base} emptyLabel={<p>Nothing yet.</p>}>
        content
      </QueryState>,
    )
    expect(screen.getByText('content')).toBeTruthy()
  })

  describe('delay window (fake timers)', () => {
    beforeEach(() => {
      vi.useFakeTimers()
    })
    afterEach(() => {
      vi.useRealTimers()
    })

    it('is announced immediately but shows no loader during the delay, then the loader', () => {
      render(
        <QueryState {...base} isPending label="Loading users…">
          content
        </QueryState>,
      )
      const status = screen.getByRole('status')
      expect(status.getAttribute('aria-busy')).toBe('true')
      expect(status.textContent).toContain('Loading users…') // sr-only announcement
      expect(screen.queryByTestId('loader')).toBeNull() // nothing visual yet
      act(() => {
        vi.advanceTimersByTime(200)
      })
      expect(screen.getByTestId('loader')).toBeTruthy()
    })

    it('a query that resolves inside the delay never renders the loader at all', () => {
      const { rerender } = render(
        <QueryState {...base} isPending>
          content
        </QueryState>,
      )
      act(() => {
        vi.advanceTimersByTime(100)
      })
      rerender(<QueryState {...base}>content</QueryState>)
      act(() => {
        vi.advanceTimersByTime(300)
      })
      expect(screen.queryByTestId('loader')).toBeNull()
      expect(screen.getByText('content')).toBeTruthy()
    })

    it('sr-only label defaults to Loading…', () => {
      render(
        <QueryState {...base} isPending>
          content
        </QueryState>,
      )
      expect(screen.getByRole('status').textContent).toContain('Loading…')
    })
  })
})
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `npx vitest run src/shared/ui/query-state.test.tsx`
Expected: FAIL — cannot resolve `./query-state`.

- [ ] **Step 3: Write the implementation**

Create `frontend/src/shared/ui/query-state.tsx`:

```tsx
import { useEffect, useState, type ReactNode } from 'react'
import { Button } from './button'

type Props = {
  isPending: boolean
  isError?: boolean
  isEmpty?: boolean
  /** A loader from skeleton / skeleton-layouts / spinner, shaped like the content. */
  loading: ReactNode
  errorLabel: string
  emptyLabel?: ReactNode
  onRetry?: () => void
  /** Screen-reader announcement; visual loaders are aria-hidden. */
  label?: string
  delayMs?: number
  children: ReactNode
}

/** Standard async-region wrapper. Precedence: error → pending → empty → children.
 * Settled children render bare (no wrapper) so flex/grid parents are untouched;
 * children entrances stay owned by the pages (animate-fade-in-up, motion). */
export function QueryState(props: Props) {
  const { isPending, isError = false, isEmpty = false, delayMs = 160 } = props
  const showLoader = useDelayedFlag(isPending, delayMs)
  if (isError) {
    return <QueryStateError label={props.errorLabel} onRetry={props.onRetry} />
  }
  if (isPending) {
    return (
      <div role="status" aria-live="polite" aria-busy="true">
        <span className="sr-only">{props.label ?? 'Loading…'}</span>
        {showLoader ? (
          <div aria-hidden="true" className="animate-fade-in-up">
            {props.loading}
          </div>
        ) : null}
      </div>
    )
  }
  if (isEmpty && props.emptyLabel != null) return <>{props.emptyLabel}</>
  return <>{props.children}</>
}

/** The empty-state geometry LibraryGrid already uses, carrying the error. */
function QueryStateError({ label, onRetry }: { label: string; onRetry?: () => void }) {
  return (
    <div
      role="alert"
      className="rounded-lg border border-dashed border-border px-4 py-10 text-center"
    >
      <p className="text-sm text-destructive">{label}</p>
      {onRetry ? (
        <Button type="button" variant="outline" size="sm" className="mt-3" onClick={onRetry}>
          Retry
        </Button>
      ) : null}
    </div>
  )
}

/** True once `active` has held for delayMs — queries that settle inside the
 * window (react-query cache, warm local API) never flash a loader. A
 * minimum-display floor was considered and dropped (spec §4.1). */
function useDelayedFlag(active: boolean, delayMs: number): boolean {
  const [shown, setShown] = useState(false)
  // Render-time reset (React's adjust-state-on-prop-change pattern), so a
  // re-entered pending state starts a fresh delay window.
  if (!active && shown) setShown(false)
  useEffect(() => {
    if (!active) return
    const timer = window.setTimeout(() => setShown(true), delayMs)
    return () => window.clearTimeout(timer)
  }, [active, delayMs])
  return shown
}
```

Add to `frontend/src/shared/ui/index.ts`:

```ts
export { QueryState } from './query-state'
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `npx vitest run src/shared/ui/query-state.test.tsx`
Expected: PASS. Also run `npx vitest run src/shared/ui` to confirm nothing else broke.

- [ ] **Step 5: Lint, typecheck, commit**

Run: `npm run lint && npm run build`, then:

```bash
cat > /tmp/msg.txt <<'EOF'
feat: add QueryState wrapper with anti-flicker delay, retry and a11y states
EOF
bash scripts/git-commit-clean.sh /tmp/msg.txt
git log -1 --format=%B
```

---

### Task 5: Adopt on the four admin table pages

Pattern for all four: keep the heading/filters rendered (they are static chrome — a UX improvement over today's whole-page early-return, and the skeleton then stands in for exactly the table it precedes); wrap only the async region; guard children with `{data ? … : null}` (TS narrowing — `QueryState` only shows children when settled, but the compiler can't know that).

**Files:**
- Modify: `frontend/src/features/admin/components/users/UsersPage.tsx`
- Modify: `frontend/src/features/admin/components/toolcalls/ToolCallsPage.tsx`
- Modify: `frontend/src/features/admin/components/settings/SettingsPage.tsx`
- Modify: `frontend/src/features/admin/components/catalog/CatalogPage.tsx`
- Test (regression, unchanged): `UsersPage.test.tsx`, `SettingsPage.test.tsx` in the same folders

**Interfaces:**
- Consumes: `QueryState`, `SkeletonTable` from `@/shared/ui`; `refetch` from each page's existing `useQuery` hook (all four hooks return the query result directly, so `refetch` is already available).
- Produces: no component-prop changes.

- [ ] **Step 1: UsersPage**

Destructure `refetch` at line 9: `const { data, isLoading, error, refetch } = useAdminUsers(page.limit, page.offset)`. Delete the two early-returns (lines 16–21). Add `import { QueryState, SkeletonTable } from '@/shared/ui'`. Wrap the async region:

```tsx
  return (
    <section>
      <h1 className="mb-1 text-lg font-semibold">Users</h1>
      <p className="mb-4 text-sm text-muted-foreground">
        Membership changes here are an operator override — membership will be
        Stripe-managed later. Soft-deleted users stay listed and can be restored.
      </p>
      <QueryState
        isPending={isLoading}
        isError={Boolean(error) || (!isLoading && !data)}
        loading={<SkeletonTable rows={8} cols={6} />}
        errorLabel="Couldn't load users."
        label="Loading users…"
        onRetry={() => void refetch()}
      >
        {data ? (
          <>
            <UsersTable users={data.items} memberships={memberships} />
            <PaginationControls
              total={data.total}
              limit={page.limit}
              offset={page.offset}
              onPrev={page.prev}
              onNext={() => page.next(data.total)}
            />
          </>
        ) : null}
      </QueryState>
    </section>
  )
```

- [ ] **Step 2: ToolCallsPage**

Destructure `refetch` at line 12. Delete the early-returns (lines 19–24). Add `import { QueryState, SkeletonTable } from '@/shared/ui'`. `<h1>` and `<ToolCallFilters …>` stay above the wrapper (filters now stay usable during a load); the rows `div`, its inline "No tool calls match the filters." paragraph, and `PaginationControls` move inside `{data ? (<>…</>) : null}` unchanged. QueryState props: `isPending={isLoading}`, `isError={Boolean(error) || (!isLoading && !data)}`, `loading={<SkeletonTable rows={6} cols={5} />}`, `errorLabel="Couldn't load tool calls."`, `label="Loading tool calls…"`, `onRetry={() => void refetch()}`. (The inline empty paragraph stays in children rather than moving to `isEmpty` — moving it would also hide the pagination when empty, a behaviour change this plan doesn't make.)

- [ ] **Step 3: SettingsPage**

Destructure `refetch` at line 5. Delete the early-returns (lines 6–11). Add `import { QueryState, SkeletonTable } from '@/shared/ui'`. `<h1>` and the description `<p>` stay above; the `overflow-x-auto` table div moves inside `{data ? (…) : null}` unchanged. Props: `loading={<SkeletonTable rows={10} cols={5} />}`, `errorLabel="Couldn't load settings."`, `label="Loading settings…"`, same `isPending`/`isError`/`onRetry` shape as Step 1.

- [ ] **Step 4: CatalogPage**

Destructure `refetch` at line 7. Delete the early-returns (lines 9–14). Add `import { QueryState, SkeletonTable } from '@/shared/ui'`. The header row (h1 + Add model button) and `{adding && <AddModelForm …/>}` stay above; the `space-y-6` providers div moves inside `{data ? (…) : null}`. Props: `loading={<SkeletonTable rows={6} cols={5} />}`, `errorLabel="Couldn't load the model catalog."`, `label="Loading catalog…"`.

- [ ] **Step 5: Run the regression tests unchanged**

Run: `npx vitest run src/features/admin`
Expected: PASS with zero test edits (they `findBy…` loaded content; none assert the old loading/error strings — verified by grep during planning). If one fails, stop and report.

- [ ] **Step 6: Lint, typecheck, commit**

Run: `npm run lint && npm run build`, then:

```bash
cat > /tmp/msg.txt <<'EOF'
refactor: adopt QueryState with table skeletons on the admin pages
EOF
bash scripts/git-commit-clean.sh /tmp/msg.txt
git log -1 --format=%B
```

---

### Task 6: Adopt on PoliciesPage and UsagePage

**Files:**
- Modify: `frontend/src/features/admin/components/policies/PoliciesPage.tsx`
- Create: `frontend/src/features/admin/components/policies/TierGrid.tsx` (extraction — keeps both files inside the 110-line / 60-line limits)
- Modify: `frontend/src/features/usage/components/UsagePage.tsx`
- Test (regression, unchanged): `PoliciesPage.test.tsx`, `QuotaSection.test.tsx`, `src/features/usage/components/UsagePage.test.tsx`

**Interfaces:**
- Consumes: `QueryState`, `SkeletonRows` from `@/shared/ui`; `MembershipPoliciesResponse` (`@/features/admin/api/membershipPolicies`), `MembershipQuotasResponse` (`@/features/admin/api/membershipQuotas`), `AdminMembership` (`@/features/admin/api/memberships`), `MeUsage` (`../api/meUsage`).
- Produces: `TierGrid` — `({ allTiers, data, quotas }: { allTiers: AdminMembership[]; data: MembershipPoliciesResponse; quotas: MembershipQuotasResponse | null }) => JSX.Element`.

- [ ] **Step 1: Extract TierGrid**

Create `frontend/src/features/admin/components/policies/TierGrid.tsx`, moving `blankPolicy` and the tier-mapping grid out of `PoliciesPage.tsx` verbatim:

```tsx
import type { AdminMembership } from '@/features/admin/api/memberships'
import type {
  MembershipPoliciesResponse,
  MembershipPolicy,
} from '@/features/admin/api/membershipPolicies'
import type { MembershipQuotasResponse } from '@/features/admin/api/membershipQuotas'
import { PolicyCard } from './PolicyCard'
import { QuotaSection } from './QuotaSection'
import { TierActions } from './TierActions'

/** A tier with no policy row yet renders all-blank (every field inherits). */
function blankPolicy(slug: string): MembershipPolicy {
  return {
    membership: slug,
    updated_at: '',
    max_tool_iters: null,
    max_external_calls: null,
    max_turn_tokens_in: null,
    max_turn_tokens_out: null,
    max_turn_cost_usd: null,
    run_deadline_seconds: null,
    max_hitl_rounds: null,
  }
}

export function TierGrid({
  allTiers,
  data,
  quotas,
}: {
  allTiers: AdminMembership[]
  data: MembershipPoliciesResponse
  quotas: MembershipQuotasResponse | null
}) {
  return (
    <div className="grid gap-4 lg:grid-cols-2">
      {allTiers.map((tier) => {
        const policy =
          data.policies.find((p) => p.membership === tier.slug) ?? blankPolicy(tier.slug)
        return (
          <div key={tier.slug} className={tier.is_active ? '' : 'opacity-60'}>
            <PolicyCard
              policy={policy}
              inherited={data.inherited}
              header={<TierActions tier={tier} allTiers={allTiers} />}
            >
              {quotas ? (
                <QuotaSection
                  membership={tier.slug}
                  kinds={quotas.kinds}
                  rows={quotas.quotas.filter((q) => q.membership === tier.slug)}
                />
              ) : null}
            </PolicyCard>
          </div>
        )
      })}
    </div>
  )
}
```

- [ ] **Step 2: Rewrite PoliciesPage around QueryState**

Replace `PoliciesPage.tsx` with:

```tsx
import { useState } from 'react'
import { useMemberships } from '@/features/admin/hooks/useMemberships'
import { useMembershipPolicies } from '@/features/admin/hooks/useMembershipPolicies'
import { useMembershipQuotas } from '@/features/admin/hooks/useMembershipQuotas'
import { QueryState, SkeletonRows } from '@/shared/ui'
import { TierFormDialog } from './TierFormDialog'
import { TierGrid } from './TierGrid'

export function PoliciesPage() {
  const tiers = useMemberships()
  const policies = useMembershipPolicies()
  const quotas = useMembershipQuotas()
  const [creating, setCreating] = useState(false)
  const isPending = policies.isLoading || tiers.isLoading
  const isError =
    Boolean(policies.error || tiers.error) ||
    (!isPending && (!policies.data || !tiers.data))
  return (
    <section>
      <div className="mb-1 flex items-center justify-between">
        <h1 className="text-lg font-semibold">Membership tiers</h1>
        <button
          type="button"
          className="rounded-md bg-primary px-3 py-1.5 text-sm text-primary-foreground"
          onClick={() => setCreating(true)}
        >
          New tier
        </button>
      </div>
      <p className="mb-4 text-sm text-muted-foreground">
        Per-turn caps: blank = inherit the runtime setting. Quotas: blank = unlimited, 0 =
        blocked. Changes apply on the user&apos;s next turn — no restart.
      </p>
      <QueryState
        isPending={isPending}
        isError={isError}
        loading={<SkeletonRows count={2} height="h-64" />}
        errorLabel="Couldn't load membership policies."
        label="Loading membership policies…"
        onRetry={() => {
          void policies.refetch()
          void tiers.refetch()
        }}
      >
        {policies.data && tiers.data ? (
          <TierGrid
            allTiers={tiers.data.memberships}
            data={policies.data}
            quotas={quotas.data ?? null}
          />
        ) : null}
      </QueryState>
      <TierFormDialog mode="create" open={creating} onClose={() => setCreating(false)} />
    </section>
  )
}
```

(Note the original destructured `const { data, isLoading, error } = useMembershipPolicies()`; the rewrite holds the whole query as `policies` so both `refetch`es can be called from `onRetry`.)

- [ ] **Step 3: UsagePage**

Rewrite `frontend/src/features/usage/components/UsagePage.tsx` — the outer padded container always renders; the data-dependent content moves to a local `UsageContent`:

```tsx
import type { MeUsage } from '../api/meUsage'
import { QueryState, SkeletonRows } from '@/shared/ui'
import { useMeUsage } from '../hooks/useMeUsage'
import { resetLabel } from '../logic/format'
import { MeterRow } from './MeterRow'
import { PlansSection } from './PlansSection'
import { StorageSection } from './StorageSection'

export function UsagePage() {
  const { data, isPending, isError, refetch } = useMeUsage()
  return (
    <div className="mx-auto max-w-xl space-y-6 p-6">
      <QueryState
        isPending={isPending}
        isError={isError || (!isPending && !data)}
        loading={<SkeletonRows count={3} height="h-12" />}
        errorLabel="Couldn't load usage."
        label="Loading usage…"
        onRetry={() => void refetch()}
      >
        {data ? <UsageContent data={data} /> : null}
      </QueryState>
    </div>
  )
}

function UsageContent({ data }: { data: MeUsage }) {
  const monthly = data.kinds.filter((k) => k.window === 'month')
  const standing = data.kinds.filter((k) => k.window === 'standing')
  return (
    <>
      <header className="space-y-1">
        <h1 className="text-lg font-semibold">Plan &amp; usage</h1>
        <p className="text-sm text-muted-foreground">
          <span>{data.membership_label}</span> plan · Usage resets{' '}
          {resetLabel(data.resets_at)}
        </p>
        {data.exempt && (
          <p className="text-xs text-muted-foreground">No limits apply (admin).</p>
        )}
      </header>
      <section className="space-y-3">
        <h2 className="text-sm font-semibold">This month</h2>
        {monthly.map((kind) => (
          <MeterRow key={kind.kind} kind={kind} />
        ))}
      </section>
      <StorageSection kinds={standing} />
      <PlansSection />
    </>
  )
}
```

- [ ] **Step 4: Run the regression tests unchanged**

Run: `npx vitest run src/features/admin/components/policies src/features/usage`
Expected: PASS with zero edits (both suites `findBy…` loaded content; `UsagePage.test.tsx` asserts on meters and labels only).

- [ ] **Step 5: Lint, typecheck, commit**

Run: `npm run lint && npm run build`, then:

```bash
cat > /tmp/msg.txt <<'EOF'
refactor: adopt QueryState on policies and usage pages
EOF
bash scripts/git-commit-clean.sh /tmp/msg.txt
git log -1 --format=%B
```

---

### Task 7: Adopt in the library feature (grid + chapter rows)

**Files:**
- Modify: `frontend/src/features/library/components/book/useLibraryPageState.ts` (expose `refetch`)
- Modify: `frontend/src/features/library/components/book/LibraryPage.tsx` (pass `pageSize` + `onRetry`)
- Modify: `frontend/src/features/library/components/book/LibraryGrid.tsx`
- Modify: `frontend/src/features/library/components/book/ChapterRows.tsx`

**Interfaces:**
- Consumes: `QueryState`, `SkeletonCards`, `InlineLoader` from `@/shared/ui`.
- Produces: `LibraryGrid`'s `Props` gains `pageSize: number` and `onRetry: () => void` (its only caller is `LibraryPage`, updated here). `useLibraryPageState`'s return gains `refetch` (react-query's, from `useBooks`). `ChapterRows` props unchanged.

- [ ] **Step 1: Expose refetch from useLibraryPageState**

In `useLibraryPageState.ts` line 9: `const { data, isLoading, isError, refetch } = useBooks()`, and add `refetch,` to the returned object (next to `isError`).

- [ ] **Step 2: LibraryPage passes the new props**

In `LibraryPage.tsx`, add to the `<LibraryGrid …>` call (after `isError`):

```tsx
          pageSize={state.pageSize}
          onRetry={() => void state.refetch()}
```

- [ ] **Step 3: Rewrite LibraryGrid's states**

In `LibraryGrid.tsx`, add `import { QueryState, SkeletonCards } from '@/shared/ui'`, add `pageSize: number` and `onRetry: () => void` to `Props`, and replace the body of `LibraryGrid` (the three early-returns + grid) with:

```tsx
export function LibraryGrid(props: Props) {
  return (
    <QueryState
      isPending={props.isLoading}
      isError={props.isError}
      loading={<SkeletonCards count={props.pageSize} />}
      errorLabel="Couldn't load library."
      label="Loading books…"
      onRetry={props.onRetry}
    >
      {props.empty ? (
        <p className="rounded-lg border border-dashed border-border px-4 py-10 text-center text-sm text-muted-foreground">
          No books yet. Add one or scrape a novel to get started.
        </p>
      ) : (
        <motion.div
          className="grid auto-rows-40 grid-cols-1 gap-x-4 gap-y-4 pt-1 sm:grid-cols-2 xl:grid-cols-3"
          variants={list}
          initial="hidden"
          animate="show"
        >
          {props.books.map((book) => (
            <motion.div key={book.id} variants={item} className="h-full overflow-visible">
              <BookCard
                book={book}
                onOpen={props.onOpen}
                onEdit={props.onEdit}
                onRead={props.onRead}
                onDelete={props.onDelete}
                isDeleting={props.isDeleting}
              />
            </motion.div>
          ))}
        </motion.div>
      )}
    </QueryState>
  )
}
```

(The bespoke empty state stays in children — spec §5 keeps it; the motion stagger keeps owning the content entrance.)

- [ ] **Step 4: ChapterRows**

In `ChapterRows.tsx`, add `import { InlineLoader, QueryState } from '@/shared/ui'` and replace the early-return + return with the table wrapped:

```tsx
export function ChapterRows(props: Props) {
  return (
    <QueryState
      isPending={props.loading}
      loading={<InlineLoader label="Loading chapters…" />}
      errorLabel="Couldn't load chapters."
      label="Loading chapters…"
    >
      <div className="min-h-0 flex-1 overflow-y-auto rounded-md border border-border">
        <table className="w-full text-sm">…(existing thead/tbody unchanged)…</table>
      </div>
    </QueryState>
  )
}
```

(No `isError` is passed — `ChaptersModal` doesn't surface one today; wiring that up is a behaviour change beyond this spec. The settled children render bare, so the `min-h-0 flex-1` div stays a direct flex child of the modal column.)

- [ ] **Step 5: Verify**

Run: `npx vitest run src/features/library` (if any tests exist there), then `npm run lint && npm run build && npm run test`
Expected: all clean/green with zero test edits.

- [ ] **Step 6: Commit**

```bash
cat > /tmp/msg.txt <<'EOF'
refactor: adopt QueryState with card skeletons in the library feature
EOF
bash scripts/git-commit-clean.sh /tmp/msg.txt
git log -1 --format=%B
```

---

### Task 8: Adopt in downloads, scraping and chapter-new

**Files:**
- Modify: `frontend/src/features/downloads/components/ready-files/ReadyFilesList.tsx`
- Modify: `frontend/src/features/downloads/components/ready-files/ReadyFilesModal.tsx` (pass `onRetry`)
- Modify: `frontend/src/features/scraping/components/ScrapeJobList.tsx`
- Modify: `frontend/src/features/library/components/chapter/ChapterNewPage.tsx`

**Interfaces:**
- Consumes: `QueryState`, `SkeletonRows`, `InlineLoader` from `@/shared/ui`.
- Produces: `ReadyFilesList`'s `Props` gains `onRetry: () => void` (only caller: `ReadyFilesModal`). Everything else keeps its props.

- [ ] **Step 1: ReadyFilesList**

Add `import { QueryState, SkeletonRows } from '@/shared/ui'`, add `onRetry: () => void` to `Props` (and to the destructuring), and replace the body:

```tsx
  return (
    <div className="mt-4 space-y-2">
      <QueryState
        isPending={loading}
        isError={errored}
        isEmpty={jobs.length === 0}
        loading={<SkeletonRows count={3} height="h-10" />}
        errorLabel="Couldn't load jobs."
        emptyLabel={<p className="text-sm text-muted-foreground">No jobs yet for this book.</p>}
        label="Loading jobs…"
        onRetry={onRetry}
      >
        <ul className="space-y-2">
          {jobs.map((job) => (
            <ReadyJobRow
              key={job.id}
              bookId={bookId}
              job={job}
              canListen={canListen}
              onListen={() => onListen(job)}
            />
          ))}
        </ul>
      </QueryState>
    </div>
  )
```

In `ReadyFilesModal.tsx`, add to the `<ReadyFilesList …>` props: `onRetry={() => void jobsQuery.refetch()}`.

- [ ] **Step 2: ScrapeJobList**

Add `import { InlineLoader, QueryState } from '@/shared/ui'` (keep the `ListPagination` import) and replace the three conditionals (loading paragraph, empty paragraph, `items.length > 0` fragment) with one wrapper — the `h2` stays above it:

```tsx
      <QueryState
        isPending={state.isLoading}
        isEmpty={state.items.length === 0}
        loading={<InlineLoader label="Loading jobs…" />}
        errorLabel="Couldn't load jobs."
        emptyLabel={<p className="text-sm text-muted-foreground">No scrape jobs yet.</p>}
        label="Loading jobs…"
      >
        <div ref={listSlotRef} className="min-h-0 flex-1 overflow-hidden">
          <ul className="space-y-2">…(existing ScrapeJobRow map unchanged)…</ul>
        </div>
        <div className="shrink-0">
          <ListPagination
            page={state.page}
            pageCount={state.pageCount}
            total={state.items.length}
            pageSize={state.pageSize}
            onPage={state.setPage}
          />
        </div>
      </QueryState>
```

(No `isError` — `useScrapeJobListState` doesn't expose one today. Children render as a bare fragment, so the flex column layout is preserved exactly as the current `<>…</>`.)

- [ ] **Step 3: ChapterNewPage**

Add `import { InlineLoader, QueryState } from '@/shared/ui'` and replace the early-return (lines 22–24) with:

```tsx
  if (bookQuery.isLoading) {
    return (
      <QueryState
        isPending
        loading={<InlineLoader label="Loading…" />}
        errorLabel="Couldn't load the book."
      >
        {null}
      </QueryState>
    )
  }
```

(This site keeps the early-return shape — the whole page depends on the book — but gains the announced status wrapper and the standard loader. `label` defaults to 'Loading…'.)

- [ ] **Step 4: Verify**

Run: `npm run lint && npm run build && npm run test`
Expected: all clean/green with zero test edits.

- [ ] **Step 5: Commit**

```bash
cat > /tmp/msg.txt <<'EOF'
refactor: adopt QueryState in downloads, scraping and chapter-new
EOF
bash scripts/git-commit-clean.sh /tmp/msg.txt
git log -1 --format=%B
```

---

### Task 9: Completion sweep

**Files:** none created — verification only.

- [ ] **Step 1: No hand-written loading/error paragraphs left in the 11 adopted files**

Run from `frontend/`:

```bash
grep -rnE 'text-(muted-foreground|destructive)">(Loading|Failed to load|Could not load)' \
  src/features/admin/components/users/UsersPage.tsx \
  src/features/admin/components/catalog/CatalogPage.tsx \
  src/features/admin/components/settings/SettingsPage.tsx \
  src/features/admin/components/policies/PoliciesPage.tsx \
  src/features/admin/components/toolcalls/ToolCallsPage.tsx \
  src/features/usage/components/UsagePage.tsx \
  src/features/library/components/book/LibraryGrid.tsx \
  src/features/library/components/book/ChapterRows.tsx \
  src/features/library/components/chapter/ChapterNewPage.tsx \
  src/features/scraping/components/ScrapeJobList.tsx \
  src/features/downloads/components/ready-files/ReadyFilesList.tsx
```

Expected: no hits. (Other files — auth guards, reader pages, `UsageSummaryTiles` — still have loading paragraphs; they are outside the spec's inventory and stay.)

- [ ] **Step 2: Error copy is uniform**

Run: `grep -rn "Failed to load\|Could not load" src/features/`
Expected: any remaining hits are only in out-of-scope files (auth guards / reader). All adopted sites now say "Couldn't load X."

- [ ] **Step 3: Full quality gates**

Run: `npm run lint && npm run build && npm run test`
Expected: all clean/green.

- [ ] **Step 4: Manual visual check**

Run the app (backend + `npm run dev`), throttle the network in devtools, and confirm: admin pages show the table skeleton (no layout jump when rows land), the library shows the card-grid skeleton at the page size, fast cached navigations show **no** flash of skeleton, and a killed backend shows the dashed error box with a working Retry. Record observations for the human reviewer.

- [ ] **Step 5: Commit (only if the sweep changed anything)**

```bash
cat > /tmp/msg.txt <<'EOF'
refactor: fixups from query-state adoption sweep
EOF
bash scripts/git-commit-clean.sh /tmp/msg.txt
git log -1 --format=%B
```
