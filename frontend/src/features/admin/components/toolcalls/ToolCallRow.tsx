import type { ToolCall } from '@/features/admin/api/toolCalls'
import { JsonBlock } from '@/features/admin/components/common/JsonBlock'

export function ToolCallRow({ call }: { call: ToolCall }) {
  return (
    <div className="rounded-lg border border-border/70 p-3 text-sm">
      <div className="flex flex-wrap items-center gap-2">
        <span className="font-mono text-xs font-medium">{call.tool_name}</span>
        <span className="rounded bg-muted px-1.5 py-0.5 text-xs">{call.status}</span>
        <span className="rounded bg-muted px-1.5 py-0.5 text-xs">{call.risk_level}</span>
        {call.confirmed_by_user && (
          <span className="rounded bg-emerald-500/15 px-1.5 py-0.5 text-xs text-emerald-600">
            confirmed
          </span>
        )}
        <span className="ml-auto text-xs text-muted-foreground">
          {call.duration_ms !== null ? `${call.duration_ms}ms · ` : ''}
          {new Date(call.created_at).toLocaleString()}
        </span>
      </div>
      <p className="mt-1 text-xs text-muted-foreground">user: {call.user_id ?? '—'}</p>
      <div className="mt-2 space-y-1">
        <JsonBlock label="Input" value={call.input} />
        <JsonBlock label="Output" value={call.output} />
      </div>
      {call.error ? <p className="mt-1 text-xs text-destructive">{call.error}</p> : null}
    </div>
  )
}
