import type { ExecutionFilters as Filters } from '@/features/admin/api/usage'
import { Input, Select } from '@/shared/ui'

const STATUSES = ['ok', 'error'] as const

export function ExecutionFilters({
  filters,
  onChange,
}: {
  filters: Filters
  onChange: (next: Filters) => void
}) {
  return (
    <div className="flex flex-wrap items-center gap-2">
      <Input
        size="sm"
        className="w-40 sm:w-48"
        placeholder="Username or email"
        aria-label="Filter by username"
        value={filters.q ?? ''}
        onChange={(event) => onChange({ ...filters, q: event.target.value })}
      />
      <Input
        size="sm"
        className="w-32 sm:w-40"
        placeholder="Task"
        aria-label="Filter by task"
        value={filters.task ?? ''}
        onChange={(event) => onChange({ ...filters, task: event.target.value })}
      />
      <Select
        size="sm"
        aria-label="Filter by status"
        value={filters.status ?? ''}
        onChange={(event) =>
          onChange({ ...filters, status: event.target.value || undefined })
        }
      >
        <option value="">Any status</option>
        {STATUSES.map((status) => (
          <option key={status} value={status}>
            {status}
          </option>
        ))}
      </Select>
    </div>
  )
}
