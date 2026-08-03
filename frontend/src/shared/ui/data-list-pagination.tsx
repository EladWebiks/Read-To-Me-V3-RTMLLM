import { ListPagination } from '@/shared/ui/list-pagination'

/** Offset/limit pager for backend Page[T] envelopes (wraps ListPagination). */
export function DataListPagination({
  total,
  limit,
  offset,
  onPage,
}: {
  total: number
  limit: number
  offset: number
  onPage: (page: number) => void
}) {
  const size = Math.max(1, limit)
  const page = total === 0 ? 1 : Math.floor(offset / size) + 1
  const pageCount = Math.max(1, Math.ceil(total / size))

  return (
    <ListPagination
      page={page}
      pageCount={pageCount}
      total={total}
      pageSize={size}
      onPage={onPage}
    />
  )
}
