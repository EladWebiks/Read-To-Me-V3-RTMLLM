import type { ModelAdmin } from '@/features/admin/api/catalog'
import { usePatchModel } from '@/features/admin/hooks/useCatalog'
import { FormError } from '@/shared/ui'
import { PricingCells } from './PricingCells'

export function ModelRow({ provider, model }: { provider: string; model: ModelAdmin }) {
  const patch = usePatchModel()
  return (
    <tr
      className={`border-t border-border/50 ${model.effective_enabled ? '' : 'opacity-60'}`}
    >
      <td className="px-3 py-1.5 font-mono text-xs">{model.model_name}</td>
      <td className="px-3 py-1.5 text-xs text-muted-foreground">
        {model.capabilities.join(', ')}
      </td>
      <PricingCells provider={provider} model={model} />
      <td className="px-3 py-1.5">
        <input
          type="checkbox"
          checked={model.enabled}
          aria-label={`Enable ${model.model_name}`}
          onChange={(event) =>
            patch.mutate({
              provider,
              modelName: model.model_name,
              body: { enabled: event.target.checked },
            })
          }
        />
        <FormError error={patch.error} />
      </td>
    </tr>
  )
}
