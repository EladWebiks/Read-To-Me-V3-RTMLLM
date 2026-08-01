import { useState } from 'react'
import { useSetUserQuota, useUserQuotas } from '@/features/admin/hooks/useUserQuotas'
import { parseQuotaInput } from '@/features/admin/logic/quotaFields'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  FormError,
  TextField,
} from '@/shared/ui'

type Props = {
  userId: string
  username: string
  open: boolean
  onOpenChange: (open: boolean) => void
}

/** Registry-driven per-user overrides; they win over the user's tier limits.
 * Blank = tier default (placeholder shows it); a number = override (0 = blocked). */
export function UserQuotasDialog({ userId, username, open, onOpenChange }: Props) {
  const { data } = useUserQuotas(userId, open)
  const save = useSetUserQuota(userId)
  const [invalid, setInvalid] = useState<string | null>(null)
  const overrideOf = (kind: string) =>
    data?.overrides.find((row) => row.quota_kind === kind)?.limit_value

  const commit = (kind: string, raw: string) => {
    const parsed = parseQuotaInput(raw)
    setInvalid(parsed.ok ? null : parsed.error)
    if (!parsed.ok) return
    if (parsed.value === null) {
      if (overrideOf(kind) !== undefined) {
        save.mutate({ kind, limit: null })
      }
      return
    }
    if (parsed.value !== overrideOf(kind)) {
      save.mutate({ kind, limit: parsed.value })
    }
  }

  const tierPlaceholder = (limit: number | undefined) =>
    limit === undefined ? 'Unlimited (tier)' : `${limit.toLocaleString('en-US')} (tier)`

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Quota overrides — {username}</DialogTitle>
        </DialogHeader>
        <p className="text-xs text-muted-foreground">
          Blank uses the {data?.membership ?? ''} tier limit. Admins stay exempt.
        </p>
        <div className="space-y-3">
          {data?.kinds.map((kind) => (
            <TextField
              key={kind.kind}
              id={`quota-${kind.kind}`}
              label={`${kind.label} (${kind.unit})`}
              numeric
              defaultValue={overrideOf(kind.kind) ?? ''}
              placeholder={tierPlaceholder(data.tier_limits[kind.kind])}
              onBlur={(event) => commit(kind.kind, event.target.value)}
            />
          ))}
        </div>
        <FormError error={invalid ?? save.error} />
      </DialogContent>
    </Dialog>
  )
}
