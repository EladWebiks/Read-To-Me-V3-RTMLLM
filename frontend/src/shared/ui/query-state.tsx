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
        <Button
          type="button"
          variant="outline"
          size="sm"
          className="mt-3"
          onClick={onRetry}
        >
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
