import { useState } from 'react'
import type {
  MembershipQuotaRow,
  QuotaKindInfo,
} from '@/features/admin/api/membershipQuotas'
import { useSaveQuota } from '@/features/admin/hooks/useMembershipQuotas'
import { parseQuotaInput } from '@/features/admin/logic/quotaFields'
import { FormError, TextField } from '@/shared/ui'

type Props = { membership: string; kinds: QuotaKindInfo[]; rows: MembershipQuotaRow[] }

function initialDrafts(kinds: QuotaKindInfo[], rows: MembershipQuotaRow[]) {
  const byKind = new Map(rows.map((r) => [r.quota_kind, r.limit_value]))
  return Object.fromEntries(
    kinds.map((k) => [k.kind, byKind.has(k.kind) ? String(byKind.get(k.kind)) : '']),
  )
}

function labelFor(meta: QuotaKindInfo) {
  const window = meta.window === 'month' ? ' / month' : ', standing'
  return `${meta.label} (${meta.unit}${window})`
}

export function QuotaSection({ membership, kinds, rows }: Props) {
  const [drafts, setDrafts] = useState(() => initialDrafts(kinds, rows))
  const save = useSaveQuota()
  const current = new Map(rows.map((r) => [r.quota_kind, r.limit_value]))
  // Derived during render — the draft text is the only source of truth.
  const parsed = new Map(
    kinds.map((k) => [k.kind, parseQuotaInput(drafts[k.kind] ?? '')]),
  )
  const errorFor = (kind: string) => {
    const result = parsed.get(kind)
    return result && !result.ok ? result.error : null
  }
  const blocked = kinds.some((k) => errorFor(k.kind) !== null)

  const onSave = () => {
    for (const meta of kinds) {
      const result = parsed.get(meta.kind)
      if (result?.ok && result.value !== (current.get(meta.kind) ?? null)) {
        save.mutate({ membership, kind: meta.kind, limit: result.value })
      }
    }
  }

  return (
    <div className="mt-3 border-t border-border/60 pt-3">
      <p className="mb-2 text-sm font-medium">Quotas (blank = unlimited, 0 = blocked)</p>
      <div className="grid gap-2 sm:grid-cols-2">
        {kinds.map((meta) => (
          <TextField
            key={meta.kind}
            id={`quota-${membership}-${meta.kind}`}
            label={labelFor(meta)}
            numeric
            value={drafts[meta.kind] ?? ''}
            placeholder={current.has(meta.kind) ? '' : 'unlimited'}
            error={errorFor(meta.kind)}
            onChange={(event) =>
              setDrafts((prev) => ({ ...prev, [meta.kind]: event.target.value }))
            }
          />
        ))}
      </div>
      <button
        type="button"
        className="mt-3 rounded-md bg-primary px-3 py-1.5 text-sm text-primary-foreground disabled:opacity-50"
        disabled={save.isPending || blocked}
        onClick={onSave}
      >
        {save.isPending ? 'Saving…' : 'Save quotas'}
      </button>
      <FormError className="mt-2" error={save.error} />
    </div>
  )
}
