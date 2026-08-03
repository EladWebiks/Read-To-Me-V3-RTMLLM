import type { ToolCall } from '@/features/admin/api/toolCalls'
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/shared/ui'

export function ToolCallDetailsDialog({
  call,
  open,
  onOpenChange,
}: {
  call: ToolCall | null
  open: boolean
  onOpenChange: (open: boolean) => void
}) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>Tool call details</DialogTitle>
          {call ? (
            <p className="font-mono text-xs text-muted-foreground">{call.tool_name}</p>
          ) : null}
        </DialogHeader>
        {call ? <ToolCallDetailsBody call={call} /> : null}
      </DialogContent>
    </Dialog>
  )
}

function ToolCallDetailsBody({ call }: { call: ToolCall }) {
  return (
    <div className="space-y-3 text-sm">
      <MetaRow call={call} />
      {call.error ? <p className="text-xs text-destructive">{call.error}</p> : null}
      <JsonSection label="Input" value={call.input} />
      <JsonSection label="Output" value={call.output} />
    </div>
  )
}

function MetaRow({ call }: { call: ToolCall }) {
  return (
    <dl className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs sm:grid-cols-3">
      <MetaItem label="Status" value={call.status} />
      <MetaItem label="Risk" value={call.risk_level} />
      <MetaItem label="Username" value={call.username ?? '—'} />
      <MetaItem label="Email" value={call.email ?? '—'} />
      <MetaItem
        label="Duration"
        value={call.duration_ms !== null ? `${call.duration_ms}ms` : '—'}
      />
      <MetaItem label="Confirmed" value={call.confirmed_by_user ? 'yes' : 'no'} />
      <MetaItem label="Time" value={new Date(call.created_at).toLocaleString()} />
    </dl>
  )
}

function MetaItem({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-muted-foreground">{label}</dt>
      <dd className="truncate font-medium">{value}</dd>
    </div>
  )
}

function JsonSection({ label, value }: { label: string; value: unknown }) {
  if (value === null || value === undefined) {
    return <p className="text-xs text-muted-foreground">{label}: —</p>
  }
  return (
    <div>
      <p className="mb-1 text-xs font-medium text-muted-foreground">{label}</p>
      <pre className="max-h-64 overflow-auto rounded bg-muted/40 p-2 text-xs">
        {JSON.stringify(value, null, 2)}
      </pre>
    </div>
  )
}
