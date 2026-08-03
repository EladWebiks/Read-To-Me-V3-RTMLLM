import type { ReactNode } from 'react'
import { Button } from '@/shared/ui'
import type { ConfirmationPayload } from '../api/chatApi'
import { hitlCardClass } from './hitlCardChrome'

type Props = {
  payload: ConfirmationPayload
  busy: boolean
  error: string | null
  onApprove: () => void
  onCancel: () => void
  children?: ReactNode
}

/** Pending HITL shell: action / title / subtitle + approve/cancel. */
export function ConfirmationPending({
  payload,
  busy,
  error,
  onApprove,
  onCancel,
  children,
}: Props) {
  const action = payload.action ?? humanizeTool(payload.tool)
  const headline = payload.title?.trim() || payload.summary
  return (
    <div className={hitlCardClass}>
      <p className="text-[11px] font-semibold uppercase tracking-wide text-violet-600 dark:text-violet-300">
        {action}
      </p>
      <p className="mt-1 text-sm font-semibold text-foreground">{headline}</p>
      {payload.subtitle ? (
        <p className="mt-0.5 text-xs text-muted-foreground">{payload.subtitle}</p>
      ) : null}
      {children}
      {error ? <p className="mt-2 text-xs text-destructive">{error}</p> : null}
      <div className="mt-3 flex gap-2">
        <Button type="button" size="sm" disabled={busy} onClick={onApprove}>
          Approve
        </Button>
        <Button
          type="button"
          size="sm"
          variant="outline"
          disabled={busy}
          onClick={onCancel}
        >
          Cancel
        </Button>
      </div>
    </div>
  )
}

export function ResolvedConfirm({ payload }: { payload: ConfirmationPayload }) {
  const label = payload.status === 'approved' ? 'Approved' : 'Declined'
  const detail = payload.title?.trim() || payload.summary
  return (
    <div className="rounded-2xl border border-border bg-muted/40 px-3.5 py-2.5 text-sm text-muted-foreground">
      <span className="font-medium text-foreground/80">{label}</span>
      {detail ? <span> — {detail}</span> : null}
    </div>
  )
}

function humanizeTool(tool: string): string {
  return tool.replaceAll('_', ' ').replace(/^\w/, (c) => c.toUpperCase())
}
