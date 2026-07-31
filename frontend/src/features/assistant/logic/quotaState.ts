/** Composer quota lock, derived DURING RENDER (never set in an effect).

Two sources (spec §3.3): a live quota_exceeded SSE error (resets_at captured
in session state) and the ['me','usage'] query — so the lock survives reload
and releases when a raised quota shows up on the next query refresh. */
import { resetLabel, type MeUsage } from '@/features/usage'

const LLM_KINDS = new Set(['llm_tokens', 'llm_cost_usd'])

export function quotaLock(
  usage: MeUsage | undefined,
  sseResetsAt: string | null,
): string | null {
  const resetsAt = sseResetsAt ?? usageBlockedResetsAt(usage)
  if (resetsAt === null) return null
  return `Monthly AI limit reached — resets ${resetLabel(resetsAt)}`
}

function usageBlockedResetsAt(usage: MeUsage | undefined): string | null {
  if (!usage || usage.exempt) return null
  const blocked = usage.kinds.some(
    (k) => LLM_KINDS.has(k.kind) && k.limit !== null && k.used >= k.limit,
  )
  return blocked ? usage.resets_at : null
}
