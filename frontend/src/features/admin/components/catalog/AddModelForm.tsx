import { useState } from 'react'
import { useCreateModel } from '@/features/admin/hooks/useCatalog'
import { CapabilityPicker } from './CapabilityPicker'
import { DraftFields, type ModelDraft } from './DraftFields'

const INITIAL_DRAFT: ModelDraft = {
  provider: 'gemini',
  model_name: '',
  context_window: '128000',
  input_cost_per_1m: '0',
  output_cost_per_1m: '0',
}

export function AddModelForm({ onDone }: { onDone: () => void }) {
  const create = useCreateModel()
  const [draft, setDraft] = useState<ModelDraft>(INITIAL_DRAFT)
  const [capabilities, setCapabilities] = useState<string[]>(['FAST_CHAT'])

  const toggle = (capability: string) => {
    setCapabilities((current) =>
      current.includes(capability)
        ? current.filter((item) => item !== capability)
        : [...current, capability],
    )
  }

  const submit = () => {
    create.mutate(
      {
        provider: draft.provider,
        model_name: draft.model_name,
        capabilities,
        context_window: Number(draft.context_window),
        input_cost_per_1m: Number(draft.input_cost_per_1m),
        output_cost_per_1m: Number(draft.output_cost_per_1m),
      },
      { onSuccess: onDone },
    )
  }

  return (
    <div className="mb-4 space-y-2 rounded-lg border border-border/70 p-3">
      <DraftFields draft={draft} onChange={setDraft} />
      <CapabilityPicker selected={capabilities} onToggle={toggle} />
      <button
        type="button"
        className="rounded-md border border-border px-2.5 py-1 text-sm hover:bg-muted"
        onClick={submit}
        disabled={create.isPending || !draft.model_name}
      >
        Create model
      </button>
      {create.error ? (
        <p className="text-xs text-destructive">{create.error.message}</p>
      ) : null}
    </div>
  )
}
