import { useState } from 'react'
import { Button } from '@/shared/ui'
import { getDownloadUrl } from '@/features/downloads/api'
import { downloadFileFromUrl } from '@/features/downloads/logic/downloadFile'
import { useDeleteDownload } from '@/features/downloads/hooks'
import type { DownloadJob } from '@/features/downloads/types'

type Props = {
  bookId: string
  job: DownloadJob
  canListen: boolean
  onListen: () => void
}

export function ReadyJobActions({ bookId, job, canListen, onListen }: Props) {
  const [downloading, setDownloading] = useState(false)
  const remove = useDeleteDownload(bookId)
  const complete = job.status === 'complete'
  const listenable = job.ready_count > 0 || complete
  return (
    <div className="flex flex-wrap gap-2">
      {canListen && listenable ? (
        <Button type="button" variant="outline" size="sm" onClick={onListen}>
          Listen
        </Button>
      ) : null}
      {complete ? (
        <Button
          type="button"
          size="sm"
          disabled={downloading}
          onClick={() => {
            setDownloading(true)
            void getDownloadUrl(job.id)
              .then((data) => downloadFileFromUrl(data.url, data.filename))
              .finally(() => setDownloading(false))
          }}
        >
          {downloading ? '…' : 'Download'}
        </Button>
      ) : null}
      <Button
        type="button"
        variant="outline"
        size="sm"
        className="text-destructive"
        disabled={remove.isPending}
        onClick={() => void remove.mutateAsync(job.id)}
      >
        Delete
      </Button>
    </div>
  )
}
