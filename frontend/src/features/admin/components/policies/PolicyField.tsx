import type { PolicyFieldMeta } from '@/features/admin/logic/policyFields'
import { placeholderFor } from '@/features/admin/logic/policyFields'
import { TextField } from '@/shared/ui'

type Props = {
  membership: string
  meta: PolicyFieldMeta
  value: string
  inherited: Record<string, number>
  onChange: (raw: string) => void
}

export function PolicyField({ membership, meta, value, inherited, onChange }: Props) {
  return (
    <TextField
      id={`policy-${membership}-${meta.key}`}
      label={meta.label}
      numeric
      value={value}
      placeholder={placeholderFor(meta, inherited)}
      onChange={(event) => onChange(event.target.value)}
    />
  )
}
