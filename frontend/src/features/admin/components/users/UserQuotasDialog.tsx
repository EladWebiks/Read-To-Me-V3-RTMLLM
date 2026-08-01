import { useState } from 'react'
import type { QuotaKindInfo } from '@/features/admin/api/membershipQuotas'
import { useSetUserQuota, useUserQuotas } from '@/features/admin/hooks/useUserQuotas'
import { parseQuotaInput } from '@/features/admin/logic/quotaFields'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  Input,
  Label,
} from '@/shared/ui'

type Props = {
  userId: string
  username: string
  open: boolean
  onOpenChange: (open: boolean) => void
}

type FieldProps = {
  kind: QuotaKindInfo
  override: number | undefined
  tierLimit: number | undefined
  onCommit: (raw: string) => void
}

/** Blank = tier default (placeholder shows it); a number = per-user override (0 = blocked). */
function QuotaOverrideField({ kind, override, tierLimit, onCommit }: FieldProps) {
  return (
    <div className="space-y-1">
      <Label htmlFor={`quota-${kind.kind}`}>
        {kind.label} ({kind.unit})
      </Label>
      <Input
        id={`quota-${kind.kind}`}
        inputMode="decimal"
        defaultValue={override ?? ''}
        placeholder={
          tierLimit === undefined
            ? 'Unlimited (tier)'
            : `${tierLimit.toLocaleString('en-US')} (tier)`
        }
        onBlur={(event) => onCommit(event.target.value)}
      />
    </div>
  )
}

/** Registry-driven per-user overrides; they win over the user's tier limits. */
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
  const message = invalid ?? save.error?.message ?? null

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
            <QuotaOverrideField
              key={kind.kind}
              kind={kind}
              override={overrideOf(kind.kind)}
              tierLimit={data.tier_limits[kind.kind]}
              onCommit={(raw) => commit(kind.kind, raw)}
            />
          ))}
        </div>
        {message ? <p className="text-xs text-destructive">{message}</p> : null}
      </DialogContent>
    </Dialog>
  )
}
