import type { ToolCall } from '@/features/admin/api/toolCalls'

/** Compact table label — username only (email lives in the details modal). */
export function toolCallUserLabel(call: ToolCall): string {
  return call.username ?? '—'
}
