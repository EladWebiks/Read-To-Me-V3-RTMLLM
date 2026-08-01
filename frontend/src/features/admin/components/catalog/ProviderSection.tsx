import type { ProviderAdmin } from '@/features/admin/api/catalog'
import { usePatchProvider } from '@/features/admin/hooks/useCatalog'
import { FormError } from '@/shared/ui'
import { ModelRow } from './ModelRow'

export function ProviderSection({ provider }: { provider: ProviderAdmin }) {
  const patch = usePatchProvider()
  return (
    <div className="rounded-lg border border-border/70">
      <div className="flex items-center gap-3 border-b border-border/60 px-3 py-2">
        <span className="font-medium">{provider.name}</span>
        {!provider.has_adapter && (
          <span className="rounded bg-destructive/15 px-1.5 py-0.5 text-xs text-destructive">
            no adapter — not served
          </span>
        )}
        <label className="ml-auto flex items-center gap-1.5 text-sm">
          <input
            type="checkbox"
            checked={provider.enabled}
            onChange={(event) =>
              patch.mutate({ name: provider.name, enabled: event.target.checked })
            }
          />
          Enabled
        </label>
      </div>
      <FormError className="px-3 py-1" error={patch.error} />
      <table className="w-full text-left text-sm">
        <thead className="text-muted-foreground">
          <tr>
            <th className="px-3 py-1.5 font-medium">Model</th>
            <th className="px-3 py-1.5 font-medium">Capabilities</th>
            <th className="px-3 py-1.5 font-medium">$/1M in</th>
            <th className="px-3 py-1.5 font-medium">$/1M out</th>
            <th className="px-3 py-1.5 font-medium">Enabled</th>
          </tr>
        </thead>
        <tbody>
          {provider.models.map((model) => (
            <ModelRow key={model.model_name} provider={provider.name} model={model} />
          ))}
        </tbody>
      </table>
    </div>
  )
}
