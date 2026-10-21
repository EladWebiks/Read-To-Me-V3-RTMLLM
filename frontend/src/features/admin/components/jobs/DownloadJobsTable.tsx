import type { DownloadJob } from '@/features/admin/api/jobs'
import {
  DataTable,
  DataTableBody,
  DataTableCell,
  DataTableColumn,
  DataTableHeader,
  DataTableRow,
} from '@/shared/ui'

export function DownloadJobsTable({ rows }: { rows: DownloadJob[] }) {
  return (
    <DataTable empty={rows.length === 0} emptyLabel="No download jobs match this filter.">
      <DataTableHeader>
        <DataTableColumn className="w-24">User</DataTableColumn>
        <DataTableColumn className="w-24">Chapters</DataTableColumn>
        <DataTableColumn>Provider</DataTableColumn>
        <DataTableColumn className="w-24">Status</DataTableColumn>
        <DataTableColumn className="w-20" hideBelow="sm">
          Progress
        </DataTableColumn>
        <DataTableColumn className="w-36" hideBelow="md">
          Created
        </DataTableColumn>
      </DataTableHeader>
      <DataTableBody>
        {rows.map((job) => (
          <DownloadJobRow key={job.id} job={job} />
        ))}
      </DataTableBody>
    </DataTable>
  )
}

function DownloadJobRow({ job }: { job: DownloadJob }) {
  return (
    <DataTableRow>
      <DataTableCell className="truncate text-xs" title={job.username ?? undefined}>
        {job.username ?? '—'}
      </DataTableCell>
      <DataTableCell className="tabular-nums text-xs">
        {job.chapter_from}–{job.chapter_to}
      </DataTableCell>
      <DataTableCell className="truncate text-xs">{job.provider}</DataTableCell>
      <DataTableCell className="truncate text-xs" title={job.error ?? job.status}>
        {job.error ?? job.status}
      </DataTableCell>
      <DataTableCell className="tabular-nums text-xs" hideBelow="sm">
        {job.ready_count}/{job.total_count}
      </DataTableCell>
      <DataTableCell
        className="tabular-nums text-xs text-muted-foreground"
        hideBelow="md"
      >
        {new Date(job.created_at).toLocaleString()}
      </DataTableCell>
    </DataTableRow>
  )
}
