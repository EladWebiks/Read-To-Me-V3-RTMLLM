import type { LlmExecutionRow } from '@/features/admin/api/usage'
import {
  DataTable,
  DataTableBody,
  DataTableCell,
  DataTableColumn,
  DataTableHeader,
  DataTableRow,
} from '@/shared/ui'

export function ExecutionsDataTable({ rows }: { rows: LlmExecutionRow[] }) {
  return (
    <DataTable empty={rows.length === 0} emptyLabel="No executions match these filters.">
      <DataTableHeader>
        <DataTableColumn className="w-40">Time</DataTableColumn>
        <DataTableColumn className="w-28">User</DataTableColumn>
        <DataTableColumn className="w-28">Task</DataTableColumn>
        <DataTableColumn>Model</DataTableColumn>
        <DataTableColumn className="w-24">Tokens</DataTableColumn>
        <DataTableColumn className="w-20" hideBelow="sm">
          Cost
        </DataTableColumn>
        <DataTableColumn className="w-20" hideBelow="md">
          Latency
        </DataTableColumn>
        <DataTableColumn className="w-16">Status</DataTableColumn>
      </DataTableHeader>
      <DataTableBody>
        {rows.map((row) => (
          <ExecutionRow key={row.id} row={row} />
        ))}
      </DataTableBody>
    </DataTable>
  )
}

function ExecutionRow({ row }: { row: LlmExecutionRow }) {
  return (
    <DataTableRow>
      <DataTableCell className="text-xs tabular-nums">
        {new Date(row.created_at).toLocaleString()}
      </DataTableCell>
      <DataTableCell className="truncate text-xs">
        {row.username ?? row.user_id.slice(0, 8)}
      </DataTableCell>
      <DataTableCell className="truncate text-xs">{row.task}</DataTableCell>
      <DataTableCell className="truncate font-mono text-xs">
        {row.provider}/{row.model}
      </DataTableCell>
      <DataTableCell className="tabular-nums text-xs">
        {row.tokens_in}/{row.tokens_out}
      </DataTableCell>
      <DataTableCell className="tabular-nums text-xs" hideBelow="sm">
        ${row.cost.toFixed(4)}
      </DataTableCell>
      <DataTableCell className="tabular-nums text-xs" hideBelow="md">
        {row.latency_ms}ms
      </DataTableCell>
      <DataTableCell className="text-xs">{row.status}</DataTableCell>
    </DataTableRow>
  )
}
