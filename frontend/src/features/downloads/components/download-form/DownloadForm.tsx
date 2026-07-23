import { useState } from 'react'
import { NumField, ProviderSelect } from './DownloadFields'
import { JobStatus } from './JobStatus'
import { useCreateDownload, useDownloadJob } from '@/features/downloads/hooks'
import type { DownloadProvider } from '@/features/downloads/types'

type DownloadFormProps = {
  bookId: string
  minChapter: number
  maxChapter: number
}

export function DownloadForm({ bookId, minChapter, maxChapter }: DownloadFormProps) {
  const [from, setFrom] = useState(minChapter)
  const [to, setTo] = useState(maxChapter)
  const [provider, setProvider] = useState<DownloadProvider>('edge')
  const [jobId, setJobId] = useState<string | null>(null)
  const create = useCreateDownload()
  const job = useDownloadJob(jobId).data

  const start = () => {
    create.mutate(
      { book_id: bookId, chapter_from: from, chapter_to: to, provider },
      { onSuccess: (created) => setJobId(created.id) },
    )
  }

  return (
    <div className="space-y-3 border border-stone-200 bg-white p-4">
      <h2 className="font-medium">Download MP3</h2>
      <div className="flex flex-wrap gap-3 text-sm">
        <NumField
          label="From"
          value={from}
          min={minChapter}
          max={maxChapter}
          onChange={setFrom}
        />
        <NumField
          label="To"
          value={to}
          min={minChapter}
          max={maxChapter}
          onChange={setTo}
        />
        <ProviderSelect value={provider} onChange={setProvider} />
        <button
          type="button"
          className="border border-stone-300 bg-stone-50 px-3 py-1 hover:bg-stone-100 disabled:opacity-50"
          disabled={create.isPending}
          onClick={start}
        >
          Start
        </button>
      </div>
      <JobStatus
        jobId={jobId}
        status={job?.status}
        ready={job?.ready_count}
        total={job?.total_count}
        error={job?.error}
      />
    </div>
  )
}
