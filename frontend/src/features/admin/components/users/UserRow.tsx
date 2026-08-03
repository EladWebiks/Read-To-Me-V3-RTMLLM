import type { AdminUser } from '@/features/admin/api/users'
import { usePatchUser } from '@/features/admin/hooks/useAdminUsers'
import { DataTableCell, DataTableRow } from '@/shared/ui'
import { CopyEmailButton } from './CopyEmailButton'
import { MembershipSelect, type MembershipOption } from './MembershipSelect'
import { UserRowActions } from './UserRowActions'

export type { MembershipOption }

export function UserRow({
  user,
  memberships,
}: {
  user: AdminUser
  memberships: MembershipOption[]
}) {
  const patch = usePatchUser()
  const deleted = user.deleted_at !== null

  const toggleAdmin = () => {
    if (
      window.confirm(`${user.is_admin ? 'Remove' : 'Grant'} admin for ${user.username}?`)
    ) {
      patch.mutate({ id: user.id, body: { is_admin: !user.is_admin } })
    }
  }

  return (
    <DataTableRow muted={deleted}>
      <DataTableCell>
        <UserIdentity user={user} deleted={deleted} />
      </DataTableCell>
      <DataTableCell className="px-2">
        <input
          type="checkbox"
          checked={user.is_admin}
          aria-label={`Admin flag for ${user.username}`}
          onChange={toggleAdmin}
        />
      </DataTableCell>
      <DataTableCell className="px-2">
        <MembershipSelect user={user} memberships={memberships} patch={patch} />
      </DataTableCell>
      <DataTableCell className="px-2 text-xs text-muted-foreground" hideBelow="md">
        {user.google_linked ? 'Yes' : '—'}
      </DataTableCell>
      <DataTableCell className="px-2 text-xs text-muted-foreground" hideBelow="lg">
        {new Date(user.created_at).toLocaleDateString()}
      </DataTableCell>
      <UserRowActions user={user} deleted={deleted} patchError={patch.error} />
    </DataTableRow>
  )
}

function UserIdentity({ user, deleted }: { user: AdminUser; deleted: boolean }) {
  return (
    <>
      <div className="flex min-w-0 items-center gap-1.5">
        <span className="truncate font-medium text-foreground">{user.username}</span>
        {deleted ? (
          <span className="shrink-0 rounded bg-destructive/15 px-1 py-px text-[10px] text-destructive">
            deleted
          </span>
        ) : null}
      </div>
      {user.email ? (
        <div className="mt-0.5 flex min-w-0 items-center gap-1">
          <span className="truncate text-xs text-muted-foreground" title={user.email}>
            {user.email}
          </span>
          <CopyEmailButton email={user.email} />
        </div>
      ) : (
        <span className="mt-0.5 block text-xs text-muted-foreground">No email</span>
      )}
    </>
  )
}
