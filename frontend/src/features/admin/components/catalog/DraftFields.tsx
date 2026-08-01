import { Input } from '@/shared/ui'

export type ModelDraft = {
  provider: string
  model_name: string
  context_window: string
  input_cost_per_1m: string
  output_cost_per_1m: string
}

const FIELDS: { key: keyof ModelDraft; label: string }[] = [
  { key: 'provider', label: 'Provider' },
  { key: 'model_name', label: 'Model name' },
  { key: 'context_window', label: 'Context window' },
  { key: 'input_cost_per_1m', label: 'Input cost per 1M' },
  { key: 'output_cost_per_1m', label: 'Output cost per 1M' },
]

export function DraftFields({
  draft,
  onChange,
}: {
  draft: ModelDraft
  onChange: (next: ModelDraft) => void
}) {
  return (
    <div className="flex flex-wrap gap-2">
      {FIELDS.map((field) => (
        <Input
          key={field.key}
          size="sm"
          value={draft[field.key]}
          aria-label={field.label}
          placeholder={field.label}
          onChange={(event) => onChange({ ...draft, [field.key]: event.target.value })}
        />
      ))}
    </div>
  )
}
