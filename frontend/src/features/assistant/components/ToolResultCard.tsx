import { Link } from 'react-router'
import { Button } from '@/shared/ui'
import type { ClientAction } from '../api/chatApi'
import { DownloadToolResultCard } from './DownloadToolResultCard'
import { hitlCardClass } from './hitlCardChrome'

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
  if (!ok) {
    return (
      <div className="rounded-2xl border border-destructive/40 bg-destructive/10 px-3.5 py-2.5 text-sm">
        <p className="text-[11px] font-semibold uppercase tracking-wide text-destructive">
          Failed
        </p>
        <p className="mt-1 text-foreground">{summary}</p>
      </div>
    )
  }
  return (
    <div className={hitlCardClass}>
      <p className="text-[11px] font-semibold uppercase tracking-wide text-violet-600 dark:text-violet-300">
        Done
      </p>
      <p className="mt-1 text-foreground">{summary}</p>
      {clientAction &&
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
      <p className="mt-1.5 text-[10px] text-muted-foreground/80">
        {name.replaceAll('_', ' ')}
      </p>
    </div>
  )
}
