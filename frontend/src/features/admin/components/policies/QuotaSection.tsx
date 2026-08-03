import { useState } from 'react'
import type {
  MembershipQuotaRow,
  QuotaKindInfo,
} from '@/features/admin/api/membershipQuotas'
import { useSaveQuota } from '@/features/admin/hooks/useMembershipQuotas'
import { parseQuotaInput } from '@/features/admin/logic/quotaFields'
import { Button, FormError, TextField } from '@/shared/ui'
import { SectionHeading } from './SectionHeading'

type Props = { membership: string; kinds: QuotaKindInfo[]; rows: MembershipQuotaRow[] }

function initialDrafts(kinds: QuotaKindInfo[], rows: MembershipQuotaRow[]) {
  const byKind = new Map(rows.map((r) => [r.quota_kind, r.limit_value]))
  return Object.fromEntries(
    kinds.map((k) => [k.kind, byKind.has(k.kind) ? String(byKind.get(k.kind)) : '']),
  )
}

function hintFor(meta: QuotaKindInfo) {
  return meta.window === 'month' ? `${meta.unit} / month` : `${meta.unit}, standing`
}

export function QuotaSection({ membership, kinds, rows }: Props) {
  const [drafts, setDrafts] = useState(() => initialDrafts(kinds, rows))
  const save = useSaveQuota()
  const current = new Map(rows.map((r) => [r.quota_kind, r.limit_value]))
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
    <section className="space-y-3 border-t border-border/70 pt-5">
      <SectionHeading
        title="Quotas"
        hint="Blank = unlimited · 0 = blocked for that kind."
      />
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
        {kinds.map((meta) => (
          <TextField
            key={meta.kind}
            id={`quota-${membership}-${meta.kind}`}
            label={meta.label}
            hint={hintFor(meta)}
            numeric
            size="sm"
            value={drafts[meta.kind] ?? ''}
            placeholder={current.has(meta.kind) ? '' : 'unlimited'}
            error={errorFor(meta.kind)}
            onChange={(event) =>
              setDrafts((prev) => ({ ...prev, [meta.kind]: event.target.value }))
            }
          />
        ))}
      </div>
      <div className="flex flex-wrap items-center gap-3 pt-1">
        <Button
          type="button"
          size="sm"
          disabled={save.isPending || blocked}
          onClick={onSave}
        >
          {save.isPending ? 'Saving…' : 'Save quotas'}
        </Button>
        <FormError error={save.error} />
      </div>
    </section>
  )
}
