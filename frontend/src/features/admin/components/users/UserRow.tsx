import { MEMBERSHIPS, type AdminUser } from '@/features/admin/api/users'
import {
  useDeleteUser,
  usePatchUser,
  useRestoreUser,
} from '@/features/admin/hooks/useAdminUsers'

function UserRowActions({
  user,
  deleted,
  patchError,
}: {
  user: AdminUser
  deleted: boolean
  patchError?: Error | null
}) {
  const remove = useDeleteUser()
  const restore = useRestoreUser()
  const error = patchError ?? remove.error ?? restore.error

  const softDelete = () => {
    if (window.confirm(`Soft-delete ${user.username}?`)) {
      remove.mutate(user.id)
    }
  }

  return (
    <td className="px-2 py-1.5">
      {deleted ? (
        <button
          type="button"
          className="text-xs underline"
          onClick={() => restore.mutate(user.id)}
        >
          Restore
        </button>
      ) : (
        <button type="button" className="text-xs underline" onClick={softDelete}>
          Delete
        </button>
      )}
      {error ? <p className="text-xs text-destructive">{error.message}</p> : null}
    </td>
  )
}

export function UserRow({ user }: { user: AdminUser }) {
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
          {MEMBERSHIPS.map((tier) => (
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
