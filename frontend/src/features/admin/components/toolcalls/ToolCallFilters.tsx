import { RISK_LEVELS, type ToolCallFilterValues } from '@/features/admin/api/toolCalls'
import { Input, Select } from '@/shared/ui'

export function ToolCallFilters({
  filters,
  onChange,
}: {
  filters: ToolCallFilterValues
  onChange: (filters: ToolCallFilterValues) => void
}) {
  return (
    <div className="flex flex-wrap items-center gap-2">
      <Input
        size="sm"
        className="w-40 sm:w-48"
        placeholder="Tool name"
        aria-label="Filter by tool name"
        value={filters.tool_name ?? ''}
        onChange={(event) => onChange({ ...filters, tool_name: event.target.value })}
      />
      <Input
        size="sm"
        className="w-32 sm:w-40"
        placeholder="Status"
        aria-label="Filter by status"
        value={filters.status ?? ''}
        onChange={(event) => onChange({ ...filters, status: event.target.value })}
      />
      <Select
        size="sm"
        aria-label="Filter by risk level"
        value={filters.risk_level ?? ''}
        onChange={(event) => onChange({ ...filters, risk_level: event.target.value })}
      >
        <option value="">Any risk</option>
        {RISK_LEVELS.map((risk) => (
          <option key={risk} value={risk}>
            {risk}
          </option>
        ))}
      </Select>
    </div>
  )
}
