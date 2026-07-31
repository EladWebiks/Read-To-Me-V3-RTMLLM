import type { PolicyFieldMeta } from '@/features/admin/logic/policyFields'
import { placeholderFor } from '@/features/admin/logic/policyFields'

type Props = {
  meta: PolicyFieldMeta
  value: string
  inherited: Record<string, number>
  onChange: (raw: string) => void
}

export function PolicyField({ meta, value, inherited, onChange }: Props) {
  return (
    <label className="flex flex-col gap-0.5 text-sm">
      <span className="text-muted-foreground">{meta.label}</span>
      <input
        className="rounded-md border border-border bg-background px-2 py-1 tabular-nums"
        inputMode="decimal"
        value={value}
        placeholder={placeholderFor(meta, inherited)}
        onChange={(event) => onChange(event.target.value)}
      />
    </label>
  )
}
