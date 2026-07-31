import { PaginationControls } from '@/features/admin/components/common/PaginationControls'
import { useDownloadJobs } from '@/features/admin/hooks/useAdminJobs'
import { usePageState } from '@/features/admin/hooks/usePageState'

export function DownloadJobsTable({ status }: { status: string }) {
  const page = usePageState(25)
  const { data } = useDownloadJobs(status, page.limit, page.offset)
  if (!data) {
    return <p className="text-sm text-muted-foreground">Loading download jobs…</p>
  }
  return (
    <div>
      <div className="overflow-x-auto">
        <table className="w-full text-left text-sm">
          <thead className="text-muted-foreground">
            <tr>
              <th className="px-2 py-1.5 font-medium">User</th>
              <th className="px-2 py-1.5 font-medium">Chapters</th>
              <th className="px-2 py-1.5 font-medium">Provider</th>
              <th className="px-2 py-1.5 font-medium">Status</th>
              <th className="px-2 py-1.5 font-medium">Progress</th>
              <th className="px-2 py-1.5 font-medium">Created</th>
            </tr>
          </thead>
          <tbody>
            {data.items.map((job) => (
              <tr key={job.id} className="border-t border-border/60">
                <td className="px-2 py-1.5 font-mono text-xs">
                  {job.user_id.slice(0, 8)}
                </td>
                <td className="px-2 py-1.5 tabular-nums">
                  {job.chapter_from}–{job.chapter_to}
                </td>
                <td className="px-2 py-1.5">{job.provider}</td>
                <td className="px-2 py-1.5">{job.error ?? job.status}</td>
                <td className="px-2 py-1.5 tabular-nums">
                  {job.ready_count}/{job.total_count}
                </td>
                <td className="px-2 py-1.5 text-muted-foreground">
                  {new Date(job.created_at).toLocaleString()}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <PaginationControls
        total={data.total}
        limit={page.limit}
        offset={page.offset}
        onPrev={page.prev}
        onNext={() => page.next(data.total)}
      />
    </div>
  )
}
