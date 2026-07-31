import { PaginationControls } from '@/features/admin/components/common/PaginationControls'
import { useAdminUsers } from '@/features/admin/hooks/useAdminUsers'
import { useMemberships } from '@/features/admin/hooks/useMemberships'
import { usePageState } from '@/features/admin/hooks/usePageState'
import { UsersTable } from './UsersTable'

export function UsersPage() {
  const page = usePageState(50)
  const { data, isLoading, error } = useAdminUsers(page.limit, page.offset)
  // Tiers come from the memberships registry — never a hardcoded list.
  const { data: membershipsData } = useMemberships()
  const memberships =
    membershipsData?.memberships.filter((m) => m.is_active).map((m) => m.slug) ?? []
  if (isLoading) {
    return <p className="text-sm text-muted-foreground">Loading users…</p>
  }
  if (error || !data) {
    return <p className="text-sm text-destructive">Failed to load users.</p>
  }
  return (
    <section>
      <h1 className="mb-1 text-lg font-semibold">Users</h1>
      <p className="mb-4 text-sm text-muted-foreground">
        Membership changes here are an operator override — membership will be
        Stripe-managed later. Soft-deleted users stay listed and can be restored.
      </p>
      <UsersTable users={data.items} memberships={memberships} />
      <PaginationControls
        total={data.total}
        limit={page.limit}
        offset={page.offset}
        onPrev={page.prev}
        onNext={() => page.next(data.total)}
      />
    </section>
  )
}
