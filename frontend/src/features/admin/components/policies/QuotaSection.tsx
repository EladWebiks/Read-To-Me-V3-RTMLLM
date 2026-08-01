import { useState } from 'react'
import type {
  MembershipQuotaRow,
  QuotaKindInfo,
} from '@/features/admin/api/membershipQuotas'
import { useSaveQuota } from '@/features/admin/hooks/useMembershipQuotas'
import { parsePolicyInput } from '@/features/admin/logic/policyFields'

type Props = { membership: string; kinds: QuotaKindInfo[]; rows: MembershipQuotaRow[] }

function initialDrafts(kinds: QuotaKindInfo[], rows: MembershipQuotaRow[]) {
  const byKind = new Map(rows.map((r) => [r.quota_kind, r.limit_value]))
  return Object.fromEntries(
    kinds.map((k) => [k.kind, byKind.has(k.kind) ? String(byKind.get(k.kind)) : '']),
  )
}

export function QuotaSection({ membership, kinds, rows }: Props) {
  const [drafts, setDrafts] = useState(() => initialDrafts(kinds, rows))
  const save = useSaveQuota()
  const current = new Map(rows.map((r) => [r.quota_kind, r.limit_value]))

  const onSave = () => {
    for (const meta of kinds) {
      const parsed = parsePolicyInput(drafts[meta.kind] ?? '')
      if (parsed === undefined) return
      if (parsed !== (current.get(meta.kind) ?? null)) {
        save.mutate({ membership, kind: meta.kind, limit: parsed })
      }
    }
  }

  return (
    <div className="mt-3 border-t border-border/60 pt-3">
      <p className="mb-2 text-sm font-medium">Quotas (blank = unlimited, 0 = blocked)</p>
      <div className="grid gap-2 sm:grid-cols-2">
        {kinds.map((meta) => (
          <label key={meta.kind} className="flex flex-col gap-0.5 text-sm">
            <span className="text-muted-foreground">
              {meta.label} ({meta.unit}
              {meta.window === 'month' ? ' / month' : ', standing'})
            </span>
            <input
              className="rounded-md border border-border bg-background px-2 py-1 tabular-nums"
              inputMode="decimal"
              value={drafts[meta.kind] ?? ''}
              placeholder={current.has(meta.kind) ? '' : 'unlimited'}
              onChange={(event) =>
                setDrafts((prev) => ({ ...prev, [meta.kind]: event.target.value }))
              }
            />
          </label>
        ))}
      </div>
      <button
        type="button"
        className="mt-3 rounded-md bg-primary px-3 py-1.5 text-sm text-primary-foreground disabled:opacity-50"
        disabled={save.isPending}
        onClick={onSave}
      >
        {save.isPending ? 'Saving…' : 'Save quotas'}
      </button>
    </div>
  )
}
