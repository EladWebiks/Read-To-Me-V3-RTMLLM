import { useState } from 'react'
import { Button } from '@/shared/ui'
import { getDownloadUrl } from '@/features/downloads/api'
import { downloadFileFromUrl } from '@/features/downloads/logic/downloadFile'
import type { ListenControlsProps } from '@/features/downloads/logic/listenControlsTypes'
import { ListenScrubber, ListenTransport } from './ListenTransport'

export type { ListenControlsProps }

export function ListenOfflineControls(props: ListenControlsProps) {
  const [downloading, setDownloading] = useState(false)
  return (
    <div className="space-y-4">
      <p className="text-sm text-muted-foreground">
        {props.current
          ? `Chapter ${props.current.chapter_number}. ${props.current.title || 'Untitled'}`
          : 'Waiting for chapters…'}
      </p>
      <p className="text-sm text-muted-foreground">
        Ready {props.readyCount}/{props.totalCount}
        {props.jobStatus ? ` · ${props.jobStatus}` : ''}
        {!props.chapterReady && props.current ? ' · synthesizing…' : ''}
      </p>
      {props.error && <p className="text-sm text-destructive">{props.error}</p>}
      <ListenScrubber {...props} />
      <ListenTransport {...props} />
      {props.jobStatus === 'complete' && (
        <Button
          variant="link"
          size="sm"
          disabled={downloading}
          onClick={() => {
            setDownloading(true)
            void getDownloadUrl(props.jobId)
              .then((data) => downloadFileFromUrl(data.url, data.filename))
              .catch((err: unknown) => console.error(err))
              .finally(() => setDownloading(false))
          }}
        >
          {downloading ? 'Downloading…' : 'Download combined MP3'}
        </Button>
      )}
      <div className="flex justify-end">
        <Button variant="outline" size="sm" onClick={props.onClose}>
          Close
        </Button>
      </div>
    </div>
  )
}
