import { useDownloadJobs, useScrapingJobs } from '@/features/admin/hooks/useAdminJobs'
import { Input, QueryState, SkeletonTable } from '@/shared/ui'
import { DownloadJobsTable } from './DownloadJobsTable'
import { JobsKindTabs, type JobsKind } from './JobsKindTabs'
import { ScrapingJobsTable } from './ScrapingJobsTable'

export function JobsToolbar({
  kind,
  status,
  onKind,
  onStatus,
}: {
  kind: JobsKind
  status: string
  onKind: (kind: JobsKind) => void
  onStatus: (status: string) => void
}) {
  return (
    <div className="flex flex-wrap items-center gap-2">
      <JobsKindTabs value={kind} onChange={onKind} />
      <Input
        size="sm"
        className="ml-auto w-40 sm:w-48"
        placeholder="Filter by status"
        aria-label="Filter by status"
        value={status}
        onChange={(event) => onStatus(event.target.value)}
      />
    </div>
  )
}

export function JobsBody({
  kind,
  pageSize,
  scraping,
  downloads,
}: {
  kind: JobsKind
  pageSize: number
  scraping: ReturnType<typeof useScrapingJobs>
  downloads: ReturnType<typeof useDownloadJobs>
}) {
  const query = kind === 'scraping' ? scraping : downloads
  return (
    <QueryState
      isPending={query.isLoading}
      isError={Boolean(query.error) || (!query.isLoading && !query.data)}
      loading={<SkeletonTable rows={Math.min(pageSize, 8)} cols={5} />}
      errorLabel="Couldn't load jobs."
      label="Loading jobs…"
      onRetry={() => void query.refetch()}
    >
      {kind === 'scraping' && scraping.data ? (
        <ScrapingJobsTable rows={scraping.data.items} />
      ) : null}
      {kind === 'downloads' && downloads.data ? (
        <DownloadJobsTable rows={downloads.data.items} />
      ) : null}
    </QueryState>
  )
}
