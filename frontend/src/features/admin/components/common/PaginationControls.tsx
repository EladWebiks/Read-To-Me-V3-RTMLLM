export function PaginationControls({
  total,
  limit,
  offset,
  onPrev,
  onNext,
}: {
  total: number
  limit: number
  offset: number
  onPrev: () => void
  onNext: () => void
}) {
  const start = total === 0 ? 0 : offset + 1
  const end = Math.min(offset + limit, total)
  return (
    <div className="flex items-center gap-3 text-sm text-muted-foreground">
      <span>
        {start}–{end} of {total}
      </span>
      <button
        type="button"
        className="underline disabled:opacity-40"
        disabled={offset === 0}
        onClick={onPrev}
      >
        Prev
      </button>
      <button
        type="button"
        className="underline disabled:opacity-40"
        disabled={offset + limit >= total}
        onClick={onNext}
      >
        Next
      </button>
    </div>
  )
}
