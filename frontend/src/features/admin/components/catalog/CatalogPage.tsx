import { useState } from 'react'
import { useCatalog } from '@/features/admin/hooks/useCatalog'
import { AddModelForm } from './AddModelForm'
import { ProviderSection } from './ProviderSection'

export function CatalogPage() {
  const { data, isLoading, error } = useCatalog()
  const [adding, setAdding] = useState(false)
  if (isLoading) {
    return <p className="text-sm text-muted-foreground">Loading catalog…</p>
  }
  if (error || !data) {
    return <p className="text-sm text-destructive">Failed to load the model catalog.</p>
  }
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
      <div className="space-y-6">
        {data.providers.map((provider) => (
          <ProviderSection key={provider.name} provider={provider} />
        ))}
      </div>
    </section>
  )
}
