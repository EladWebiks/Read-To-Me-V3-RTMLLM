import { getDownloadUrl } from '@/features/downloads/api'

export function JobStatus({
  jobId,
  status,
  ready,
  total,
  error,
}: {
  jobId: string | null
  status?: string
  ready?: number
  total?: number
  error?: string | null
}) {
  if (!jobId) {
    return null
  }
  if (status === 'complete') {
    return (
      <button
        type="button"
        className="text-sm font-medium text-foreground underline"
        onClick={() => {
          void getDownloadUrl(jobId).then((data) => {
            window.location.href = data.url
          })
        }}
      >
        Download ready — click to save
      </button>
    )
  }
  return (
    <p className="text-sm text-muted-foreground">
      Job {status ?? '…'}
      {ready != null && total != null ? ` (${ready}/${total})` : ''}
      {error ? ` — ${error}` : ''}
    </p>
  )
}
