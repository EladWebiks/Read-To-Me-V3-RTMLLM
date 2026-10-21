import type { AdminUser } from '@/features/admin/api/users'
import { DataTable, DataTableBody, DataTableColumn, DataTableHeader } from '@/shared/ui'
import { UserRow, type MembershipOption } from './UserRow'

export function UsersTable({
  users,
  memberships,
}: {
  users: AdminUser[]
  memberships: MembershipOption[]
}) {
  return (
    <DataTable empty={users.length === 0} emptyLabel="No users match these filters.">
      <DataTableHeader>
        <DataTableColumn>User</DataTableColumn>
        <DataTableColumn className="w-14 px-2">Admin</DataTableColumn>
        <DataTableColumn className="w-32 px-2">Membership</DataTableColumn>
        <DataTableColumn className="w-16 px-2" hideBelow="md">
          Google
        </DataTableColumn>
        <DataTableColumn className="w-24 px-2" hideBelow="lg">
          Created
        </DataTableColumn>
        <DataTableColumn className="w-28 px-2" srOnly>
          Actions
        </DataTableColumn>
      </DataTableHeader>
      <DataTableBody>
        {users.map((user) => (
          <UserRow key={user.id} user={user} memberships={memberships} />
        ))}
      </DataTableBody>
    </DataTable>
  )
}
