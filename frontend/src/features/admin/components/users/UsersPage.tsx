import { useRef } from 'react'
import { AdminListFrame } from '@/features/admin/components/common/AdminListFrame'
import { PaginationControls } from '@/features/admin/components/common/PaginationControls'
import { useAdminTablePageSize } from '@/features/admin/hooks/useAdminTablePageSize'
import { useAdminUsers } from '@/features/admin/hooks/useAdminUsers'
import { useMemberships } from '@/features/admin/hooks/useMemberships'
import { usePageState } from '@/features/admin/hooks/usePageState'
import { useViewportLock } from '@/shared/hooks/useViewportLock'
import { QueryState, SkeletonTable } from '@/shared/ui'
import { UsersTable } from './UsersTable'

const ROW_REM = 2.5
const HEADER_REM = 2.25

export function UsersPage() {
  const sectionRef = useRef<HTMLElement>(null)
  const slotRef = useRef<HTMLDivElement>(null)
  useViewportLock(sectionRef)
  const pageSize = useAdminTablePageSize(slotRef, {
    rowRem: ROW_REM,
    headerRem: HEADER_REM,
    fallback: 12,
  })
  const page = usePageState(pageSize)
  const { data, isLoading, error, refetch } = useAdminUsers(page.limit, page.offset)
  const { data: membershipsData } = useMemberships()
  const memberships =
    membershipsData?.memberships
      .filter((m) => m.is_active)
      .map((m) => ({ slug: m.slug, label: m.label })) ?? []

  return (
    <AdminListFrame
      sectionRef={sectionRef}
      title="Users"
      description="Membership changes here are an operator override — membership will be Stripe-managed later. Soft-deleted users stay listed and can be restored."
      slotRef={slotRef}
      footer={
        data ? (
          <PaginationControls
            total={data.total}
            limit={page.limit}
            offset={page.offset}
            onPrev={page.prev}
            onNext={() => page.next(data.total)}
          />
        ) : (
          <span className="text-sm text-muted-foreground">—</span>
        )
      }
    >
      <QueryState
        isPending={isLoading}
        isError={Boolean(error) || (!isLoading && !data)}
        loading={<SkeletonTable rows={Math.min(pageSize, 8)} cols={6} />}
        errorLabel="Couldn't load users."
        label="Loading users…"
        onRetry={() => void refetch()}
      >
        {data ? <UsersTable users={data.items} memberships={memberships} /> : null}
      </QueryState>
    </AdminListFrame>
  )
}
