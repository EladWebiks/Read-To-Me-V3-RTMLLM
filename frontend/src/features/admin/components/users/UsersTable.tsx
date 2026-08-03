import type { AdminUser } from '@/features/admin/api/users'
import { UserRow, type MembershipOption } from './UserRow'

export function UsersTable({
  users,
  memberships,
}: {
  users: AdminUser[]
  memberships: MembershipOption[]
}) {
  return (
    <div className="h-full overflow-auto">
      <table className="w-full text-left text-sm">
        <thead className="sticky top-0 bg-background text-muted-foreground">
          <tr>
            <th className="px-2 py-1.5 font-medium">Username</th>
            <th className="px-2 py-1.5 font-medium">Email</th>
            <th className="px-2 py-1.5 font-medium">Admin</th>
            <th className="px-2 py-1.5 font-medium">Membership</th>
            <th className="px-2 py-1.5 font-medium">Google</th>
            <th className="px-2 py-1.5 font-medium">Created</th>
            <th className="px-2 py-1.5 font-medium">Actions</th>
          </tr>
        </thead>
        <tbody>
          {users.map((user) => (
            <UserRow key={user.id} user={user} memberships={memberships} />
          ))}
        </tbody>
      </table>
    </div>
  )
}
