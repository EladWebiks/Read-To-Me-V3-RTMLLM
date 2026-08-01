import { useState } from 'react'
import type { ModelAdmin } from '@/features/admin/api/catalog'
import { usePatchModel } from '@/features/admin/hooks/useCatalog'
import { FormError, Input } from '@/shared/ui'

/** The two pricing cells of a model row; saves both values together. */
export function PricingCells({
  provider,
  model,
}: {
  provider: string
  model: ModelAdmin
}) {
  const patch = usePatchModel()
  const [costIn, setCostIn] = useState(String(model.input_cost_per_1m))
  const [costOut, setCostOut] = useState(String(model.output_cost_per_1m))
  const dirty =
    Number(costIn) !== model.input_cost_per_1m ||
    Number(costOut) !== model.output_cost_per_1m

  const savePricing = () => {
    patch.mutate({
      provider,
      modelName: model.model_name,
      body: { input_cost_per_1m: Number(costIn), output_cost_per_1m: Number(costOut) },
    })
  }

  return (
    <>
      <td className="px-3 py-1.5">
        <Input
          size="sm"
          className="w-20"
          value={costIn}
          onChange={(event) => setCostIn(event.target.value)}
          aria-label={`Input cost for ${model.model_name}`}
        />
      </td>
      <td className="px-3 py-1.5">
        <Input
          size="sm"
          className="w-20"
          value={costOut}
          onChange={(event) => setCostOut(event.target.value)}
          aria-label={`Output cost for ${model.model_name}`}
        />
        {dirty && (
          <button type="button" className="ml-2 text-xs underline" onClick={savePricing}>
            Save
          </button>
        )}
        <FormError error={patch.error} />
      </td>
    </>
  )
}
