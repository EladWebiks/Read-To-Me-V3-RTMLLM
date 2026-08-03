import type { ScrapeJob } from '@/features/admin/api/jobs'
import {
  DataTable,
  DataTableBody,
  DataTableCell,
  DataTableColumn,
  DataTableHeader,
  DataTableRow,
} from '@/shared/ui'

export function ScrapingJobsTable({ rows }: { rows: ScrapeJob[] }) {
  return (
    <DataTable empty={rows.length === 0} emptyLabel="No scraping jobs match this filter.">
      <DataTableHeader>
        <DataTableColumn>Book</DataTableColumn>
        <DataTableColumn className="w-24">User</DataTableColumn>
        <DataTableColumn className="w-24">Status</DataTableColumn>
        <DataTableColumn className="w-20" hideBelow="sm">
          Progress
        </DataTableColumn>
        <DataTableColumn className="w-36" hideBelow="md">
          Updated
        </DataTableColumn>
        <DataTableColumn className="w-40" hideBelow="lg">
          Message
        </DataTableColumn>
      </DataTableHeader>
      <DataTableBody>
        {rows.map((job) => (
          <ScrapingJobRow key={job.id} job={job} />
        ))}
      </DataTableBody>
    </DataTable>
  )
}

function ScrapingJobRow({ job }: { job: ScrapeJob }) {
  const book = job.book_title ?? job.start_url
  const note = job.error ?? job.message ?? '—'
  return (
    <DataTableRow>
      <DataTableCell className="truncate text-xs" title={book}>
        {book}
      </DataTableCell>
      <DataTableCell className="truncate text-xs" title={job.username ?? undefined}>
        {job.username ?? '—'}
      </DataTableCell>
      <DataTableCell className="truncate text-xs">{job.status}</DataTableCell>
      <DataTableCell className="tabular-nums text-xs" hideBelow="sm">
        {job.chapters_done} ch
      </DataTableCell>
      <DataTableCell
        className="tabular-nums text-xs text-muted-foreground"
        hideBelow="md"
      >
        {new Date(job.updated_at).toLocaleString()}
      </DataTableCell>
      <DataTableCell
        className="truncate text-xs text-muted-foreground"
        hideBelow="lg"
        title={note}
      >
        {note}
      </DataTableCell>
    </DataTableRow>
  )
}
