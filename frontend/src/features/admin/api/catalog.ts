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
