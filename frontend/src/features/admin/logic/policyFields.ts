export type PolicyFieldKey =
  | 'max_tool_iters'
  | 'max_external_calls'
  | 'max_turn_tokens_in'
  | 'max_turn_tokens_out'
  | 'max_turn_cost_usd'
  | 'run_deadline_seconds'
  | 'max_hitl_rounds'

export type PolicyFieldMeta = {
  key: PolicyFieldKey
  /** All fields here are per-turn caps: null = inherit the runtime setting. */
  label: string
}

export const POLICY_FIELDS: PolicyFieldMeta[] = [
  { key: 'max_tool_iters', label: 'Max tool iterations / turn' },
  { key: 'max_external_calls', label: 'Max external calls / turn' },
  { key: 'max_turn_tokens_in', label: 'Max tokens in / turn' },
  { key: 'max_turn_tokens_out', label: 'Max tokens out / turn' },
  { key: 'max_turn_cost_usd', label: 'Max cost (USD) / turn' },
  { key: 'run_deadline_seconds', label: 'Run deadline (seconds)' },
  { key: 'max_hitl_rounds', label: 'Max confirmation rounds / turn' },
]

/** '' -> null (inherit); invalid -> undefined (block save). */
export function parsePolicyInput(raw: string): number | null | undefined {
  const trimmed = raw.trim()
  if (trimmed === '') return null
  const value = Number(trimmed)
  return Number.isFinite(value) && value >= 0 ? value : undefined
}

export function placeholderFor(
  meta: PolicyFieldMeta,
  inherited: Record<string, number>,
): string {
  const value = inherited[meta.key]
  return `inherit (${value ?? '—'})`
}
