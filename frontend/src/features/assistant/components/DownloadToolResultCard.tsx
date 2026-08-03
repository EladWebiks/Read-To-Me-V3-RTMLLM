import { useCallback, useEffect, useRef, useState } from 'react'
import { Button } from '@/shared/ui'
import { getDownloadUrl } from '@/features/downloads/api'
import { useDownloadJob } from '@/features/downloads/hooks'
import { downloadFileFromUrl } from '@/features/downloads/logic/downloadFile'
import type { DownloadClientAction } from '../api/chatTypes'
import { hitlCardClass } from './hitlCardChrome'

type Props = {
  action: DownloadClientAction
  summary: string
}

export function DownloadToolResultCard({ action, summary }: Props) {
  const job = useDownloadJob(action.jobId).data
  const [error, setError] = useState<string | null>(null)
  const [downloading, setDownloading] = useState(false)
  const autoDownloaded = useRef(false)
  const complete = job?.status === 'complete'

  const download = useCallback(async () => {
    setDownloading(true)
    setError(null)
    try {
      const data = await getDownloadUrl(action.jobId)
      await downloadFileFromUrl(data.url, data.filename)
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Download failed')
    } finally {
      setDownloading(false)
    }
  }, [action.jobId])

  useEffect(() => {
    if (!complete || autoDownloaded.current) return
    autoDownloaded.current = true
    void download()
  }, [complete, download])

  return (
    <div className={hitlCardClass}>
      <p className="text-[11px] font-semibold uppercase tracking-wide text-violet-600 dark:text-violet-300">
        Audio download
      </p>
      <p className="mt-1 text-foreground">{summary}</p>
      <DownloadProgress
        status={job?.status}
        ready={job?.ready_count ?? 0}
        total={job?.total_count ?? action.chapterTo - action.chapterFrom + 1}
      />
      {error ? <p className="mt-2 text-xs text-destructive">{error}</p> : null}
      {complete ? (
        <Button
          type="button"
          variant="outline"
          size="sm"
          className="mt-2"
          disabled={downloading}
          onClick={() => void download()}
        >
          {downloading ? 'Downloading…' : 'Download MP3'}
        </Button>
      ) : null}
    </div>
  )
}

function DownloadProgress({
  status,
  ready,
  total,
}: {
  status?: string
  ready: number
  total: number
}) {
  const safeTotal = Math.max(total, 1)
  const percent = Math.min(100, Math.round((ready / safeTotal) * 100))
  const label =
    status === 'failed'
      ? 'Generation failed'
      : status === 'complete'
        ? 'Ready — download started'
        : `Generating audio… ${ready}/${total}`
  return (
    <div className="mt-2 space-y-1">
      <p className="text-xs text-muted-foreground">{label}</p>
      <div className="h-1.5 overflow-hidden rounded-full bg-muted">
        <div
          className="h-full bg-primary transition-all"
          style={{ width: `${percent}%` }}
        />
      </div>
    </div>
  )
}
