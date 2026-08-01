import { useState } from 'react'
import type { AdminUser } from '@/features/admin/api/users'
import { useDeleteUser, useRestoreUser } from '@/features/admin/hooks/useAdminUsers'
import { FormError } from '@/shared/ui'
import { UserQuotasDialog } from './UserQuotasDialog'

/** Per-row controls: quota overrides, soft-delete/restore, and error text. */
export function UserRowActions({
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
  const [quotasOpen, setQuotasOpen] = useState(false)
  const error = patchError ?? remove.error ?? restore.error

  const softDelete = () => {
    if (window.confirm(`Soft-delete ${user.username}?`)) {
      remove.mutate(user.id)
    }
  }

  return (
    <td className="px-2 py-1.5">
      <button
        type="button"
        className="mr-2 text-xs underline"
        onClick={() => setQuotasOpen(true)}
      >
        Quotas
      </button>
      <UserQuotasDialog
        userId={user.id}
        username={user.username}
        open={quotasOpen}
        onOpenChange={setQuotasOpen}
      />
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
      <FormError error={error} />
    </td>
  )
}
