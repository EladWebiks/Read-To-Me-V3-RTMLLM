import type { ToolCall } from '@/features/admin/api/toolCalls'
import {
  Button,
  DataTable,
  DataTableBody,
  DataTableCell,
  DataTableColumn,
  DataTableHeader,
  DataTableRow,
} from '@/shared/ui'
import { toolCallUserLabel } from './toolCallUserLabel'

export function ToolCallsDataTable({
  rows,
  onDetails,
}: {
  rows: ToolCall[]
  onDetails: (call: ToolCall) => void
}) {
  return (
    <DataTable empty={rows.length === 0} emptyLabel="No tool calls match these filters.">
      <DataTableHeader>
        <DataTableColumn>Tool</DataTableColumn>
        <DataTableColumn className="w-28">Status</DataTableColumn>
        <DataTableColumn className="w-28" hideBelow="md">
          Risk
        </DataTableColumn>
        <DataTableColumn className="w-24">User</DataTableColumn>
        <DataTableColumn className="w-16" hideBelow="sm">
          Duration
        </DataTableColumn>
        <DataTableColumn className="w-36" hideBelow="lg">
          Time
        </DataTableColumn>
        <DataTableColumn className="w-20" srOnly>
          Actions
        </DataTableColumn>
      </DataTableHeader>
      <DataTableBody>
        {rows.map((row) => (
          <ToolCallTableRow key={row.id} row={row} onDetails={onDetails} />
        ))}
      </DataTableBody>
    </DataTable>
  )
}

function ToolCallTableRow({
  row,
  onDetails,
}: {
  row: ToolCall
  onDetails: (call: ToolCall) => void
}) {
  return (
    <DataTableRow>
      <DataTableCell className="truncate font-mono text-xs" title={row.tool_name}>
        {row.tool_name}
      </DataTableCell>
      <DataTableCell className="truncate text-xs" title={row.status}>
        {row.status}
      </DataTableCell>
      <DataTableCell className="truncate text-xs" hideBelow="md" title={row.risk_level}>
        {row.risk_level}
      </DataTableCell>
      <DataTableCell className="truncate text-xs" title={toolCallUserLabel(row)}>
        {toolCallUserLabel(row)}
      </DataTableCell>
      <DataTableCell className="tabular-nums text-xs" hideBelow="sm">
        {row.duration_ms !== null ? `${row.duration_ms}ms` : '—'}
      </DataTableCell>
      <DataTableCell className="tabular-nums text-xs" hideBelow="lg">
        {new Date(row.created_at).toLocaleString()}
      </DataTableCell>
      <DataTableCell>
        <Button type="button" variant="outline" size="sm" onClick={() => onDetails(row)}>
          Details
        </Button>
      </DataTableCell>
    </DataTableRow>
  )
}
