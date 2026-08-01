import { useState } from 'react'
import { useCatalog } from '@/features/admin/hooks/useCatalog'
import { QueryState, SkeletonTable } from '@/shared/ui'
import { AddModelForm } from './AddModelForm'
import { ProviderSection } from './ProviderSection'

export function CatalogPage() {
  const { data, isLoading, error, refetch } = useCatalog()
  const [adding, setAdding] = useState(false)
  return (
    <section>
      <div className="mb-3 flex items-center justify-between">
        <h1 className="text-lg font-semibold">LLM model catalog</h1>
        <button
          type="button"
          className="rounded-md border border-border px-2.5 py-1 text-sm hover:bg-muted"
          onClick={() => setAdding((value) => !value)}
        >
          {adding ? 'Close' : 'Add model'}
        </button>
      </div>
      {adding && <AddModelForm onDone={() => setAdding(false)} />}
      <QueryState
        isPending={isLoading}
        isError={Boolean(error) || (!isLoading && !data)}
        loading={<SkeletonTable rows={6} cols={5} />}
        errorLabel="Couldn't load the model catalog."
        label="Loading catalog…"
        onRetry={() => void refetch()}
      >
        {data ? (
          <div className="space-y-6">
            {data.providers.map((provider) => (
              <ProviderSection key={provider.name} provider={provider} />
            ))}
          </div>
        ) : null}
      </QueryState>
    </section>
  )
}
