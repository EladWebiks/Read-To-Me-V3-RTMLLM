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
  /** Short label — units / inherit rules live in `hint`. */
  label: string
  hint: string
}

export const POLICY_FIELDS: PolicyFieldMeta[] = [
  { key: 'max_tool_iters', label: 'Tool iterations', hint: 'Per turn' },
  { key: 'max_external_calls', label: 'External calls', hint: 'Per turn' },
  { key: 'max_turn_tokens_in', label: 'Tokens in', hint: 'Per turn' },
  { key: 'max_turn_tokens_out', label: 'Tokens out', hint: 'Per turn' },
  { key: 'max_turn_cost_usd', label: 'Cost (USD)', hint: 'Per turn' },
  { key: 'run_deadline_seconds', label: 'Run deadline', hint: 'Seconds' },
  { key: 'max_hitl_rounds', label: 'Confirmation rounds', hint: 'Per turn' },
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
