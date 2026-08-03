import { useState } from 'react'
import type { AdminUser } from '@/features/admin/api/users'
import { useDeleteUser, useRestoreUser } from '@/features/admin/hooks/useAdminUsers'
import { Button, DataTableCell, FormError } from '@/shared/ui'
import { UserQuotasDialog } from './UserQuotasDialog'

type Props = {
  user: AdminUser
  deleted: boolean
  patchError?: Error | null
}

/** Per-row controls: quota overrides, soft-delete/restore, and error text. */
export function UserRowActions({ user, deleted, patchError }: Props) {
  const remove = useDeleteUser()
  const restore = useRestoreUser()
  const [quotasOpen, setQuotasOpen] = useState(false)
  const error = patchError ?? remove.error ?? restore.error

  return (
    <DataTableCell className="px-1.5">
      <div className="flex flex-wrap items-center justify-end gap-0.5">
        <RowAction label="Quotas" onClick={() => setQuotasOpen(true)} />
        <UserQuotasDialog
          userId={user.id}
          username={user.username}
          open={quotasOpen}
          onOpenChange={setQuotasOpen}
        />
        {deleted ? (
          <RowAction label="Restore" onClick={() => restore.mutate(user.id)} />
        ) : (
          <RowAction
            label="Delete"
            onClick={() => {
              if (window.confirm(`Soft-delete ${user.username}?`)) remove.mutate(user.id)
            }}
          />
        )}
      </div>
      <FormError error={error} />
    </DataTableCell>
  )
}

function RowAction({ label, onClick }: { label: string; onClick: () => void }) {
  return (
    <Button
      type="button"
      variant="ghost"
      size="sm"
      className="h-6 px-1.5 text-[11px]"
      onClick={onClick}
    >
      {label}
    </Button>
  )
}
