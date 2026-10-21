import type { AdminUserFilters } from '@/features/admin/api/users'
import { Input, Select } from '@/shared/ui'

type MembershipOption = { slug: string; label: string }

type Props = {
  filters: AdminUserFilters
  memberships: MembershipOption[]
  onChange: (next: AdminUserFilters) => void
}

export function UsersFilters({ filters, memberships, onChange }: Props) {
  return (
    <div className="flex flex-wrap items-center gap-2">
      <Input
        size="sm"
        className="w-44 sm:w-56"
        placeholder="Search user or email"
        aria-label="Search users"
        value={filters.q ?? ''}
        onChange={(event) => onChange({ ...filters, q: event.target.value })}
      />
      <MembershipFilter filters={filters} memberships={memberships} onChange={onChange} />
      <StatusFilter filters={filters} onChange={onChange} />
      <AdminFilter filters={filters} onChange={onChange} />
      <SortFilter filters={filters} onChange={onChange} />
    </div>
  )
}

function MembershipFilter({ filters, memberships, onChange }: Props) {
  return (
    <Select
      size="sm"
      aria-label="Filter by membership"
      value={filters.membership ?? ''}
      onChange={(event) =>
        onChange({ ...filters, membership: event.target.value || undefined })
      }
    >
      <option value="">Any membership</option>
      {memberships.map((tier) => (
        <option key={tier.slug} value={tier.slug}>
          {tier.label}
        </option>
      ))}
    </Select>
  )
}

function StatusFilter({ filters, onChange }: Omit<Props, 'memberships'>) {
  return (
    <Select
      size="sm"
      aria-label="Filter by status"
      value={filters.status ?? 'all'}
      onChange={(event) =>
        onChange({
          ...filters,
          status: event.target.value as AdminUserFilters['status'],
        })
      }
    >
      <option value="all">All statuses</option>
      <option value="active">Active</option>
      <option value="deleted">Deleted</option>
    </Select>
  )
}

function AdminFilter({ filters, onChange }: Omit<Props, 'memberships'>) {
  return (
    <Select
      size="sm"
      aria-label="Filter by admin flag"
      value={filters.admin ?? 'any'}
      onChange={(event) =>
        onChange({ ...filters, admin: event.target.value as AdminUserFilters['admin'] })
      }
    >
      <option value="any">Any role</option>
      <option value="admin">Admins</option>
      <option value="user">Non-admins</option>
    </Select>
  )
}

function SortFilter({ filters, onChange }: Omit<Props, 'memberships'>) {
  return (
    <Select
      size="sm"
      aria-label="Sort users"
      value={filters.sort ?? 'created_desc'}
      onChange={(event) =>
        onChange({ ...filters, sort: event.target.value as AdminUserFilters['sort'] })
      }
    >
      <option value="created_desc">Newest first</option>
      <option value="created_asc">Oldest first</option>
      <option value="username_asc">Username A–Z</option>
      <option value="username_desc">Username Z–A</option>
    </Select>
  )
}
