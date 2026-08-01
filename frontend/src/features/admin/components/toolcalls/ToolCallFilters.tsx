import { RISK_LEVELS, type ToolCallFilterValues } from '@/features/admin/api/toolCalls'
import { Select } from '@/shared/ui'

const FIELD = 'rounded border border-border bg-background px-2 py-1 text-sm'

export function ToolCallFilters({
  filters,
  onChange,
}: {
  filters: ToolCallFilterValues
  onChange: (filters: ToolCallFilterValues) => void
}) {
  return (
    <div className="mb-4 flex flex-wrap gap-2">
      <input
        className={FIELD}
        placeholder="Tool name"
        aria-label="Filter by tool name"
        value={filters.tool_name ?? ''}
        onChange={(event) => onChange({ ...filters, tool_name: event.target.value })}
      />
      <input
        className={FIELD}
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
