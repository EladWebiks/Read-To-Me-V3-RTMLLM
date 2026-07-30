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

const FIELD = 'rounded border border-border bg-background px-2 py-1 text-sm'

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
        <input
          key={field.key}
          className={FIELD}
          value={draft[field.key]}
          aria-label={field.label}
          placeholder={field.label}
          onChange={(event) => onChange({ ...draft, [field.key]: event.target.value })}
        />
      ))}
    </div>
  )
}
