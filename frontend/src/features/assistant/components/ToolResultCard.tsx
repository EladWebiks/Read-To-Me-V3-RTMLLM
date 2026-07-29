import { Link } from 'react-router'
import { Button } from '@/shared/ui'
import type { ClientAction } from '../api/chatApi'
import { DownloadToolResultCard } from './DownloadToolResultCard'

type Props = {
  name: string
  ok: boolean
  summary: string
  clientAction?: ClientAction
}

/** Compact durable tool outcome (e.g. scrape queued). */
export function ToolResultCard({ name, ok, summary, clientAction }: Props) {
  if (ok && clientAction?.type === 'download') {
    return <DownloadToolResultCard action={clientAction} summary={summary} />
  }
  return (
    <div
      className={
        ok
          ? 'rounded-2xl border border-border bg-muted/40 px-3.5 py-2.5 text-sm'
          : 'rounded-2xl border border-destructive/40 bg-destructive/10 px-3.5 py-2.5 text-sm'
      }
    >
      <p className="text-xs font-medium text-muted-foreground">
        {ok ? 'Done' : 'Failed'} · <span className="font-mono">{name}</span>
      </p>
      <p className="mt-1 text-foreground">{summary}</p>
      {ok &&
      clientAction &&
      clientAction.type !== 'settings' &&
      clientAction.type !== 'download' ? (
        <div className="mt-2">
          <Button asChild variant="outline" size="sm">
            <Link
              to={clientAction.path}
              state={
                clientAction.type === 'play'
                  ? { autoPlay: true, playbackRequestId: clientAction.path }
                  : undefined
              }
            >
              {clientAction.label}
            </Link>
          </Button>
        </div>
      ) : null}
    </div>
  )
}
