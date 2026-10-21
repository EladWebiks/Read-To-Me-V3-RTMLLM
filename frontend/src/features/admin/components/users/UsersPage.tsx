import { useState } from 'react'
import type { AdminUserFilters } from '@/features/admin/api/users'
import { useAdminUsers } from '@/features/admin/hooks/useAdminUsers'
import { useMemberships } from '@/features/admin/hooks/useMemberships'
import { usePageState } from '@/features/admin/hooks/usePageState'
import { useDataListLayout } from '@/shared/hooks/useDataListLayout'
import { DataListFrame } from '@/shared/ui'
import { UsersFilters } from './UsersFilters'
import { UsersBody, UsersFooter } from './UsersPageParts'

const ROW_REM = 2.5
const HEADER_REM = 2

const DEFAULT_FILTERS: AdminUserFilters = {
  status: 'all',
  admin: 'any',
  sort: 'created_desc',
}

export function UsersPage() {
  const { sectionRef, slotRef, pageSize } = useDataListLayout({
    rowRem: ROW_REM,
    headerRem: HEADER_REM,
    fallback: 10,
  })
  const [filters, setFilters] = useState<AdminUserFilters>(DEFAULT_FILTERS)
  const page = usePageState(pageSize)
  const query = useAdminUsers(page.limit, page.offset, filters)
  const memberships = useActiveMembershipOptions()

  return (
    <DataListFrame
      sectionRef={sectionRef}
      title="Users"
      description="Operator membership overrides (Stripe later). Soft-deleted users stay listed."
      toolbar={
        <UsersFilters
          filters={filters}
          memberships={memberships}
          onChange={(next) => {
            setFilters(next)
            page.reset()
          }}
        />
      }
      slotRef={slotRef}
      footer={<UsersFooter data={query.data} onPage={page.setPage} page={page} />}
    >
      <UsersBody pageSize={pageSize} query={query} memberships={memberships} />
    </DataListFrame>
  )
}

function useActiveMembershipOptions() {
  const { data } = useMemberships()
  return (
    data?.memberships
      .filter((m) => m.is_active)
      .map((m) => ({ slug: m.slug, label: m.label })) ?? []
  )
}
