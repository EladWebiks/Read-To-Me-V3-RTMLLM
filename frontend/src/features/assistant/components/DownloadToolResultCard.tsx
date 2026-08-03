import type { DownloadClientAction } from '../api/chatTypes'
import { DownloadCardActions, DownloadProgress } from './downloadCardParts'
import { hitlCardClass } from './hitlCardChrome'
import { useDownloadCardActions } from './useDownloadCardActions'

type Props = {
  action: DownloadClientAction
  summary: string
}

export function DownloadToolResultCard({ action, summary }: Props) {
  const card = useDownloadCardActions(action.jobId)
  const total = card.job?.total_count ?? action.chapterTo - action.chapterFrom + 1
  return (
    <div className={hitlCardClass}>
      <p className="text-[11px] font-semibold uppercase tracking-wide text-violet-600 dark:text-violet-300">
        Audio download
      </p>
      <p className="mt-1 text-foreground">{summary}</p>
      <DownloadProgress
        status={card.status}
        ready={card.job?.ready_count ?? 0}
        total={total}
      />
      {card.error ? <p className="mt-2 text-xs text-destructive">{card.error}</p> : null}
      <DownloadCardActions
        complete={card.complete}
        inFlight={card.inFlight}
        downloading={card.downloading}
        cancelling={card.cancelling}
        onDownload={() => void card.download()}
        onCancel={card.cancelJob}
      />
    </div>
  )
}
