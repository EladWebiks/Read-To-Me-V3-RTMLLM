# Query State & Loaders — Design

Date: 2026-08-01
Status: proposed

## 1. Goal

Replace 13 hand-written loading/error early-returns with one `QueryState`
wrapper and a small family of loaders that match the shape of whatever is
about to appear.

### 1.1 What exists today

Every async surface early-returns a bare paragraph:

```tsx
if (isLoading) return <p className="text-sm text-muted-foreground">Loading…</p>
if (error || !data) return <p className="text-sm text-destructive">Failed to load users.</p>
```

Thirteen of these, across `UsersPage`, `CatalogPage`, `SettingsPage`,
`PoliciesPage`, `ToolCallsPage`, `UsagePage`, `LibraryGrid`, `ChapterRows`,
`ChapterNewPage`, `ScrapeJobList`, `ReadyFilesList`. Four concrete problems:

1. **The copy has already drifted** — "Failed to load" vs "Could not load",
   "Loading…" vs "Loading users…".
2. **No recovery.** A failed query leaves a dead sentence; the only way out is
   a page reload. Nothing calls `refetch`.
3. **Layout shift.** A one-line paragraph is replaced by a table or a card
   grid, so the page jumps.
4. **No a11y.** Nothing announces the transition — no `role="status"`, no
   `aria-busy`. A screen reader user hears silence, then content.

## 2. Theme grounding

Everything below uses tokens and idioms already in `index.css`, not new ones.

- Palette is a warm stone scale driven by CSS variables
  (`--muted-foreground: #78716c` light / `#a8a29e` dark), so a skeleton tinted
  from `--muted-foreground` is automatically correct in both themes. **No
  `dark:` variants are needed anywhere in this design.**
- The codebase already tints with `color-mix`:
  `color-mix(in srgb, var(--muted-foreground) 14%, transparent)` for inline
  code, `18%` for reader-word hover. The skeleton reuses the 14% value.
- Custom keyframes already live in `index.css` (`fade-in-up`,
  `assistant-pulse`, `rtm-tooltip-in`). One more follows that convention and
  the `rtm-` prefix.
- Ambient loops in this app are slow and calm — `assistant-pulse` is 2.2s,
  spark twinkles 1.8–2.4s. The shimmer is 1.6s to sit in that range rather
  than the frantic ~1s default most libraries ship.
- `LoaderCircle` from lucide with `animate-spin` is **already** the spinner
  idiom (`LiveStatusLine`); this design standardises it rather than inventing.
- `index.css` already has a `@media (prefers-reduced-motion: reduce)` block —
  the new class joins it.

## 3. The loader family

Not one loader. Five, chosen by what is about to replace them.

### 3.1 `Skeleton` — the primitive

```tsx
<Skeleton className="h-4 w-32" />
```

A tinted block. All shape comes from `className`, so it composes into anything.

New CSS in `index.css`:

```css
@keyframes rtm-skeleton-sweep {
  from { background-position: -200% 0; }
  to   { background-position:  200% 0; }
}

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

Added to the existing reduced-motion block, where it degrades to the flat
`background-color` with no sweep.

### 3.2 `Spinner`

`LoaderCircle` + `animate-spin`, `size="sm" | "md"`, `aria-hidden`. For
indeterminate waits with no predictable shape — buttons, small inline areas.

**Reduced motion keeps the spinner spinning.** It is the only signal that
anything is happening, and a small rotating icon is far less provocative than
a large sweeping gradient. The shimmer is what gets disabled.

### 3.3 `SkeletonText`

```tsx
<SkeletonText lines={3} />
```

Stacked `h-4` bars; the last is 60% width so it reads as prose rather than a
block. For paragraph-shaped content.

### 3.4 `SkeletonTable`

```tsx
<SkeletonTable rows={8} cols={5} />
```

A header bar plus `rows` striped bars using the same `border-t border-border/50`
rhythm and `px-3 py-1.5` cell metrics as the real admin tables, so the swap
does not shift layout. This is the workhorse — five of the thirteen sites are
tables.

### 3.5 `SkeletonCards`

```tsx
<SkeletonCards count={6} />
```

Mirrors `LibraryGrid`'s exact grid —
`grid auto-rows-40 grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3` — with
card-shaped blocks. Count defaults to the page size so the grid does not
resize when real books land.

### 3.6 `SkeletonRows`

```tsx
<SkeletonRows count={3} height="h-12" />
```

Stacked full-width blocks for meter rows and file lists.

### 3.7 `InlineLoader`

```tsx
<InlineLoader label="Loading chapters…" />
```

`Spinner` + muted label on one line. For small areas inside an already-rendered
container (chapter rows in a modal, the scrape job list) where a skeleton would
be more furniture than the content it stands in for.

## 4. `QueryState`

```tsx
type Props = {
  isPending: boolean
  isError?: boolean
  isEmpty?: boolean
  loading: ReactNode          // a loader from §3
  errorLabel: string
  emptyLabel?: ReactNode
  onRetry?: () => void
  label?: string              // sr-only, defaults to 'Loading…'
  delayMs?: number            // defaults to 160
  children: ReactNode
}
```

Precedence: error → pending → empty → children.

`loading` is a `ReactNode`, not a variant enum. An enum would need a
per-variant props bag (`rows`, `cols`, `count`, `height`) threaded through
`QueryState`, which just relocates the complexity and makes the component know
about every layout in the app. Passing the loader keeps `QueryState` dumb.

Plain booleans in, not a react-query result object — `shared/ui` currently
imports nothing but React, `cn` and Radix, and this design keeps it that way.

### 4.1 The delay — why it is the biggest UX win here

`delayMs` (default 160) means **nothing renders for the first 160ms**. Queries
that resolve from the react-query cache or a warm local API finish inside that
window, so navigating between admin pages stops flashing skeletons on and off.
Only genuinely slow loads show a loader.

A minimum-display floor once shown was considered and dropped: it adds latency
to make an animation look nicer, and the delay alone fixes the flicker.

### 4.2 Error state

Replaces the dead sentence with the empty-state geometry `LibraryGrid` already
uses — `rounded-lg border border-dashed border-border px-4 py-10 text-center` —
carrying `errorLabel` in `text-destructive`, plus a **Retry** button when
`onRetry` is given. Every adoption site passes react-query's `refetch`, so a
failed load becomes recoverable without a reload for the first time.

The button uses shared `Button` (`variant="outline" size="sm"`), which the
admin feature does not currently use at all — noted in the duplication survey
as a separate adoption gap.

### 4.3 Accessibility

- Wrapper: `role="status"`, `aria-live="polite"`, `aria-busy={isPending}`.
- The visual loader is `aria-hidden`; an `sr-only` span carries `label`, so a
  screen reader hears "Loading users…" once rather than a pile of empty divs.
- Error state is `role="alert"` — consistent with `FormError` from the shared
  form work.
- Retry is a real `<button>`, reachable by keyboard.

### 4.4 Content entrance

`QueryState` deliberately does **not** animate `children` in. `LibraryPage`,
`ScraperPage` and `ChapterNewLayout` already use `.animate-fade-in-up`, and
`LibraryGrid` runs a `motion/react` stagger — a wrapper-level animation would
fight both. Only the loader itself fades in.

## 5. Adoption — 11 files (13 early-returns)

| site | loader |
| ---- | ------ |
| `UsersPage` | `SkeletonTable rows={8} cols={6}` |
| `ToolCallsPage` | `SkeletonTable rows={6} cols={5}` |
| `SettingsPage` | `SkeletonTable rows={10} cols={5}` |
| `CatalogPage` | `SkeletonTable rows={6} cols={5}` |
| `PoliciesPage` | `SkeletonRows count={2} height="h-64"` (two tier cards) |
| `LibraryGrid` | `SkeletonCards count={pageSize}` |
| `UsagePage` | `SkeletonRows count={3} height="h-12"` (meters) |
| `ReadyFilesList` | `SkeletonRows count={3} height="h-10"` |
| `ChapterRows` | `InlineLoader label="Loading chapters…"` |
| `ScrapeJobList` | `InlineLoader label="Loading jobs…"` |
| `ChapterNewPage` | `InlineLoader label="Loading…"` |

`LibraryGrid` keeps its own empty state (it has bespoke copy and an
illustration slot); it passes `isEmpty` only if that turns out to simplify.

Error copy is normalised to **"Couldn't load X."** at every site, replacing
today's mix of "Failed to load" and "Could not load".

## 6. Testing

New `shared/ui/query-state.test.tsx`:

- renders `children` when not pending and not errored
- renders nothing during the delay window, then the loader after it
  (fake timers)
- a query that resolves inside the delay never renders the loader at all
- error takes precedence over pending
- error renders `role="alert"` with the label, and a Retry button that calls
  `onRetry`
- no Retry button when `onRetry` is omitted
- `aria-busy` is true while pending, and the `sr-only` label is present
- `isEmpty` renders `emptyLabel`, and children win when not empty

New `shared/ui/skeleton.test.tsx`:

- `Skeleton` merges `className` onto the `rtm-skeleton` base
- `SkeletonText lines={3}` renders 3 bars, last one narrower
- `SkeletonTable rows={4} cols={3}` renders the right cell count
- `SkeletonCards count={6}` renders 6 cards
- every skeleton is `aria-hidden` so it never reaches the accessibility tree
- `InlineLoader` renders its label as text

Regression net: the 11 adoption sites' existing tests. `UsagePage.test.tsx`
and `LibraryGrid`-related tests assert on loaded content, so they should pass
unchanged; any that assert on the literal string "Loading…" will need the new
copy and are called out rather than silently rewritten.

## 7. File layout

```
shared/ui/
  skeleton.tsx        # Skeleton, SkeletonText
  skeleton-layouts.tsx# SkeletonTable, SkeletonCards, SkeletonRows
  spinner.tsx         # Spinner, InlineLoader
  query-state.tsx     # QueryState
  index.ts            # barrel
index.css             # rtm-skeleton + keyframes + reduced-motion entry
```

Split four ways to stay well inside the 110-line ESLint ceiling, and because
`query-state.tsx` holds the only stateful logic (the delay timer) while the
rest are pure presentational functions.

## 8. Out of scope

- Suspense / `useSuspenseQuery`. This is a presentational layer; changing the
  data-fetching model is a separate decision.
- Optimistic UI and stale-while-revalidate indicators (a subtle "refreshing"
  affordance when `isFetching` but not `isPending`). Worth doing later; it
  needs its own thinking about when a refresh should be visible at all.
- Progress bars. Nothing in the app reports real progress except the existing
  job-progress SSE components, which already have their own UI.
- Toasts / global error reporting.
