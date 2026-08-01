# Backoffice 04 — LLM Catalog Screen Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Frontend-only LLM catalog screen over the existing `/api/admin/llm/catalog` API: providers and models with enabled toggles (PATCH), pricing edits (PATCH), and an add-model form (POST) surfacing the API's typed capability/adapter errors inline.

**Architecture:** Zero backend work. `features/admin` gains a catalog API module, react-query hooks, and small components; the route swaps its `AdminPlaceholder`. TS types mirror `CatalogAdminResponse`/`ProviderAdminRead`/`ModelAdminRead` exactly.

**Tech Stack:** React 19, react-query, vitest.

**Spec:** `docs/superpowers/specs/2026-07-30-backoffice-mvp-design.md`. **Depends on:** `2026-07-30-backoffice-01-foundation.md` (routes/guard, `apiPatch`, `ApiError` detail parsing). Vitest coverage decision: the settings screen covers the form-screen kind — no test mandated here.

## Global Constraints

- Frontend gates (run from `frontend/`): `npm run lint`, `npm run build`, `npm run test`.
- Commit with `bash scripts/git-commit-clean.sh /tmp/msg.txt`. **Never** add attribution trailers. Verify with `git log -1 --format=%B`.
- ESLint limits: file ≤110 lines, function ≤60, nesting ≤3 (tests/barrels exempt).
- All server state via react-query; all fetching through `src/shared/lib/api.ts`; mirror backend response schemas exactly — never reshape.

---

### Task 1: LLM catalog screen

**Files:**
- Create: `frontend/src/features/admin/api/catalog.ts`
- Create: `frontend/src/features/admin/hooks/useCatalog.ts`
- Create: `frontend/src/features/admin/components/catalog/CatalogPage.tsx`
- Create: `frontend/src/features/admin/components/catalog/ProviderSection.tsx`
- Create: `frontend/src/features/admin/components/catalog/ModelRow.tsx`
- Create: `frontend/src/features/admin/components/catalog/AddModelForm.tsx`
- Create: `frontend/src/features/admin/components/catalog/CapabilityPicker.tsx`
- Modify: `frontend/src/features/admin/index.ts`
- Modify: `frontend/src/app/App.tsx` (swap the catalog placeholder)

**Interfaces:**
- Consumes: existing `GET /api/admin/llm/catalog`, `PATCH .../providers/{provider}`, `PATCH .../models/{provider}/{model_name}`, `POST .../models`; foundation's `apiPatch`.
- Produces: `CatalogPage` export.

- [ ] **Step 1: Implement the API module**

```typescript
// frontend/src/features/admin/api/catalog.ts
import { apiGet, apiPatch, apiPost } from '@/shared/lib/api'

/** Mirrors ModelAdminRead (llm/schemas.py) exactly. */
export type ModelAdmin = {
  model_name: string
  enabled: boolean
  effective_enabled: boolean
  capabilities: string[]
  context_window: number
  supports_tools: boolean
  supports_structured: boolean
  supports_streaming: boolean
  input_cost_per_1m: number
  output_cost_per_1m: number
  updated_at: string
}

/** Mirrors ProviderAdminRead exactly. */
export type ProviderAdmin = {
  name: string
  enabled: boolean
  has_adapter: boolean
  models: ModelAdmin[]
}

export type CatalogResponse = { providers: ProviderAdmin[] }

export type ModelPatchBody = {
  enabled?: boolean
  input_cost_per_1m?: number
  output_cost_per_1m?: number
}

export type ModelCreateBody = {
  provider: string
  model_name: string
  capabilities: string[]
  context_window: number
  input_cost_per_1m: number
  output_cost_per_1m: number
}

/** Mirrors ModelCapability (llm/capabilities.py). */
export const MODEL_CAPABILITIES = [
  'FAST_CHAT',
  'TOOL_CALLING',
  'STRUCTURED_EXTRACTION',
  'LONG_CONTEXT_SUMMARIZATION',
  'RERANKING',
  'EMBEDDING',
  'LOCAL_PRIVATE_INFERENCE',
] as const

const BASE = '/api/admin/llm/catalog'

export function fetchCatalog(): Promise<CatalogResponse> {
  return apiGet(BASE)
}

export function patchProvider(name: string, enabled: boolean): Promise<ProviderAdmin> {
  return apiPatch(`${BASE}/providers/${encodeURIComponent(name)}`, { enabled })
}

export function patchModel(
  provider: string,
  modelName: string,
  body: ModelPatchBody,
): Promise<ModelAdmin> {
  return apiPatch(
    `${BASE}/models/${encodeURIComponent(provider)}/${encodeURIComponent(modelName)}`,
    body,
  )
}

export function createModel(body: ModelCreateBody): Promise<ModelAdmin> {
  return apiPost(`${BASE}/models`, body)
}
```

- [ ] **Step 2: Implement the hooks**

```typescript
// frontend/src/features/admin/hooks/useCatalog.ts
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  createModel,
  fetchCatalog,
  patchModel,
  patchProvider,
  type ModelCreateBody,
  type ModelPatchBody,
} from '@/features/admin/api/catalog'

export const catalogKey = ['admin', 'llm-catalog'] as const

export function useCatalog() {
  return useQuery({ queryKey: catalogKey, queryFn: fetchCatalog })
}

function useInvalidateCatalog() {
  const queryClient = useQueryClient()
  return () => queryClient.invalidateQueries({ queryKey: catalogKey })
}

export function usePatchProvider() {
  const invalidate = useInvalidateCatalog()
  return useMutation({
    mutationFn: ({ name, enabled }: { name: string; enabled: boolean }) =>
      patchProvider(name, enabled),
    onSuccess: invalidate,
  })
}

export function usePatchModel() {
  const invalidate = useInvalidateCatalog()
  return useMutation({
    mutationFn: ({
      provider,
      modelName,
      body,
    }: {
      provider: string
      modelName: string
      body: ModelPatchBody
    }) => patchModel(provider, modelName, body),
    onSuccess: invalidate,
  })
}

export function useCreateModel() {
  const invalidate = useInvalidateCatalog()
  return useMutation({
    mutationFn: (body: ModelCreateBody) => createModel(body),
    onSuccess: invalidate,
  })
}
```

- [ ] **Step 3: Implement the components**

```tsx
// frontend/src/features/admin/components/catalog/CatalogPage.tsx
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
```

```tsx
// frontend/src/features/admin/components/catalog/ProviderSection.tsx
import type { ProviderAdmin } from '@/features/admin/api/catalog'
import { usePatchProvider } from '@/features/admin/hooks/useCatalog'
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
      {patch.error ? (
        <p className="px-3 py-1 text-xs text-destructive">{patch.error.message}</p>
      ) : null}
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
```

```tsx
// frontend/src/features/admin/components/catalog/ModelRow.tsx
import { useState } from 'react'
import type { ModelAdmin } from '@/features/admin/api/catalog'
import { usePatchModel } from '@/features/admin/hooks/useCatalog'

export function ModelRow({ provider, model }: { provider: string; model: ModelAdmin }) {
  const patch = usePatchModel()
  const [costIn, setCostIn] = useState(String(model.input_cost_per_1m))
  const [costOut, setCostOut] = useState(String(model.output_cost_per_1m))
  const dirty =
    Number(costIn) !== model.input_cost_per_1m || Number(costOut) !== model.output_cost_per_1m

  const savePricing = () => {
    patch.mutate({
      provider,
      modelName: model.model_name,
      body: { input_cost_per_1m: Number(costIn), output_cost_per_1m: Number(costOut) },
    })
  }

  const priceInput = 'w-20 rounded border border-border bg-background px-1.5 py-0.5 text-xs'
  return (
    <tr className={`border-t border-border/50 ${model.effective_enabled ? '' : 'opacity-60'}`}>
      <td className="px-3 py-1.5 font-mono text-xs">{model.model_name}</td>
      <td className="px-3 py-1.5 text-xs text-muted-foreground">
        {model.capabilities.join(', ')}
      </td>
      <td className="px-3 py-1.5">
        <input
          className={priceInput}
          value={costIn}
          onChange={(event) => setCostIn(event.target.value)}
          aria-label={`Input cost for ${model.model_name}`}
        />
      </td>
      <td className="px-3 py-1.5">
        <input
          className={priceInput}
          value={costOut}
          onChange={(event) => setCostOut(event.target.value)}
          aria-label={`Output cost for ${model.model_name}`}
        />
        {dirty && (
          <button type="button" className="ml-2 text-xs underline" onClick={savePricing}>
            Save
          </button>
        )}
      </td>
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
        {patch.error ? <p className="text-xs text-destructive">{patch.error.message}</p> : null}
      </td>
    </tr>
  )
}
```

```tsx
// frontend/src/features/admin/components/catalog/CapabilityPicker.tsx
import { MODEL_CAPABILITIES } from '@/features/admin/api/catalog'

export function CapabilityPicker({
  selected,
  onToggle,
}: {
  selected: string[]
  onToggle: (capability: string) => void
}) {
  return (
    <fieldset className="flex flex-wrap gap-x-4 gap-y-1 text-xs">
      <legend className="mb-1 text-muted-foreground">Capabilities</legend>
      {MODEL_CAPABILITIES.map((capability) => (
        <label key={capability} className="flex items-center gap-1">
          <input
            type="checkbox"
            checked={selected.includes(capability)}
            onChange={() => onToggle(capability)}
          />
          {capability}
        </label>
      ))}
    </fieldset>
  )
}
```

```tsx
// frontend/src/features/admin/components/catalog/AddModelForm.tsx
import { useState } from 'react'
import { useCreateModel } from '@/features/admin/hooks/useCatalog'
import { CapabilityPicker } from './CapabilityPicker'

const FIELD = 'rounded border border-border bg-background px-2 py-1 text-sm'

export function AddModelForm({ onDone }: { onDone: () => void }) {
  const create = useCreateModel()
  const [provider, setProvider] = useState('gemini')
  const [modelName, setModelName] = useState('')
  const [contextWindow, setContextWindow] = useState('128000')
  const [costIn, setCostIn] = useState('0')
  const [costOut, setCostOut] = useState('0')
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
        provider,
        model_name: modelName,
        capabilities,
        context_window: Number(contextWindow),
        input_cost_per_1m: Number(costIn),
        output_cost_per_1m: Number(costOut),
      },
      { onSuccess: onDone },
    )
  }

  return (
    <div className="mb-4 space-y-2 rounded-lg border border-border/70 p-3">
      <div className="flex flex-wrap gap-2">
        <input className={FIELD} value={provider} aria-label="Provider" placeholder="Provider"
          onChange={(event) => setProvider(event.target.value)} />
        <input className={FIELD} value={modelName} aria-label="Model name" placeholder="Model name"
          onChange={(event) => setModelName(event.target.value)} />
        <input className={FIELD} value={contextWindow} aria-label="Context window"
          onChange={(event) => setContextWindow(event.target.value)} />
        <input className={FIELD} value={costIn} aria-label="Input cost per 1M"
          onChange={(event) => setCostIn(event.target.value)} />
        <input className={FIELD} value={costOut} aria-label="Output cost per 1M"
          onChange={(event) => setCostOut(event.target.value)} />
      </div>
      <CapabilityPicker selected={capabilities} onToggle={toggle} />
      <button
        type="button"
        className="rounded-md border border-border px-2.5 py-1 text-sm hover:bg-muted"
        onClick={submit}
        disabled={create.isPending || !modelName}
      >
        Create model
      </button>
      {create.error ? <p className="text-xs text-destructive">{create.error.message}</p> : null}
    </div>
  )
}
```

- [ ] **Step 4: Wire the route and barrel**

Append to `frontend/src/features/admin/index.ts`:

```typescript
export { CatalogPage } from './components/catalog/CatalogPage'
```

In `frontend/src/app/App.tsx`: extend the `@/features/admin` import with `CatalogPage` and change the catalog route to:

```tsx
<Route path="catalog" element={<CatalogPage />} />
```

- [ ] **Step 5: Gates + commit**

```bash
cd frontend && npm run lint && npm run build && npm run test && cd ..
printf 'feat: add backoffice LLM catalog screen\n' > /tmp/msg.txt
git add -A
bash scripts/git-commit-clean.sh /tmp/msg.txt
git log -1 --format=%B
```
