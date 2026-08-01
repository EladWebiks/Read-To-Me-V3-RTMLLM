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
            row === 0
              ? 'flex gap-3 px-3 py-1.5'
              : 'flex gap-3 border-t border-border/50 px-3 py-1.5'
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
