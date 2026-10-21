import { useAdminUsers } from '@/features/admin/hooks/useAdminUsers'
import { DataListPagination, QueryState, SkeletonTable } from '@/shared/ui'
import { UsersTable } from './UsersTable'

export function UsersFooter({
  data,
  page,
  onPage,
}: {
  data: { total: number } | undefined
  page: { limit: number; offset: number }
  onPage: (p: number) => void
}) {
  if (!data) return <p className="text-sm text-muted-foreground">Measuring layout…</p>
  return (
    <DataListPagination
      total={data.total}
      limit={page.limit}
      offset={page.offset}
      onPage={onPage}
    />
  )
}

export function UsersBody({
  pageSize,
  query,
  memberships,
}: {
  pageSize: number
  query: ReturnType<typeof useAdminUsers>
  memberships: { slug: string; label: string }[]
}) {
  return (
    <QueryState
      isPending={query.isLoading}
      isError={Boolean(query.error) || (!query.isLoading && !query.data)}
      loading={<SkeletonTable rows={Math.min(pageSize, 8)} cols={4} />}
      errorLabel="Couldn't load users."
      label="Loading users…"
      onRetry={() => void query.refetch()}
    >
      {query.data ? (
        <UsersTable users={query.data.items} memberships={memberships} />
      ) : null}
    </QueryState>
  )
}
