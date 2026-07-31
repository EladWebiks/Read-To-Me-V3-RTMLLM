import { PaginationControls } from '@/features/admin/components/common/PaginationControls'
import { useScrapingJobs } from '@/features/admin/hooks/useAdminJobs'
import { usePageState } from '@/features/admin/hooks/usePageState'

export function ScrapingJobsTable({ status }: { status: string }) {
  const page = usePageState(25)
  const { data } = useScrapingJobs(status, page.limit, page.offset)
  if (!data) {
    return <p className="text-sm text-muted-foreground">Loading scraping jobs…</p>
  }
  return (
    <div>
      <div className="overflow-x-auto">
        <table className="w-full text-left text-sm">
          <thead className="text-muted-foreground">
            <tr>
              <th className="px-2 py-1.5 font-medium">Book</th>
              <th className="px-2 py-1.5 font-medium">User</th>
              <th className="px-2 py-1.5 font-medium">Status</th>
              <th className="px-2 py-1.5 font-medium">Progress</th>
              <th className="px-2 py-1.5 font-medium">Updated</th>
              <th className="px-2 py-1.5 font-medium">Message</th>
            </tr>
          </thead>
          <tbody>
            {data.items.map((job) => (
              <tr key={job.id} className="border-t border-border/60">
                <td className="px-2 py-1.5">{job.book_title ?? job.start_url}</td>
                <td className="px-2 py-1.5 font-mono text-xs">
                  {job.user_id.slice(0, 8)}
                </td>
                <td className="px-2 py-1.5">{job.status}</td>
                <td className="px-2 py-1.5 tabular-nums">{job.chapters_done} ch</td>
                <td className="px-2 py-1.5 text-muted-foreground">
                  {new Date(job.updated_at).toLocaleString()}
                </td>
                <td className="px-2 py-1.5 text-xs text-muted-foreground">
                  {job.error ?? job.message ?? '—'}
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
