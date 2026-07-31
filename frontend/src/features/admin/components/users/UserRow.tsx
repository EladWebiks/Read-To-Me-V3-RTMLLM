import type { AdminUser } from '@/features/admin/api/users'
import { usePatchUser } from '@/features/admin/hooks/useAdminUsers'
import { UserRowActions } from './UserRowActions'

export function UserRow({
  user,
  memberships,
}: {
  user: AdminUser
  memberships: string[]
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
    <tr className={`border-t border-border/60 ${deleted ? 'opacity-60' : ''}`}>
      <td className="px-2 py-1.5">
        {user.username}
        {deleted && (
          <span className="ml-2 rounded bg-destructive/15 px-1.5 py-0.5 text-xs text-destructive">
            deleted
          </span>
        )}
      </td>
      <td className="px-2 py-1.5 text-muted-foreground">{user.email ?? '—'}</td>
      <td className="px-2 py-1.5">
        <input
          type="checkbox"
          checked={user.is_admin}
          aria-label={`Admin flag for ${user.username}`}
          onChange={toggleAdmin}
        />
      </td>
      <td className="px-2 py-1.5">
        <select
          className="rounded border border-border bg-background px-1 py-0.5 text-xs"
          value={user.membership}
          aria-label={`Membership for ${user.username} (operator override)`}
          onChange={(event) =>
            patch.mutate({ id: user.id, body: { membership: event.target.value } })
          }
        >
          {/* While the registry loads, keep the current tier so it never blanks. */}
          {(memberships.length > 0 ? memberships : [user.membership]).map((tier) => (
            <option key={tier} value={tier}>
              {tier}
            </option>
          ))}
        </select>
      </td>
      <td className="px-2 py-1.5">{user.google_linked ? 'linked' : '—'}</td>
      <td className="px-2 py-1.5 text-muted-foreground">
        {new Date(user.created_at).toLocaleDateString()}
      </td>
      <UserRowActions user={user} deleted={deleted} patchError={patch.error} />
    </tr>
  )
}
