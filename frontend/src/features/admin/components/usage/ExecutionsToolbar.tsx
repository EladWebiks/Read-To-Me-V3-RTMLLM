import type { ExecutionFilters as Filters } from '@/features/admin/api/usage'
import { DateRangeField } from '@/features/admin/components/common/DateRangeField'
import type { Period } from '@/features/admin/logic/period'
import { ExecutionFilters } from './ExecutionFilters'
import { UsageTabs, type UsageTab } from './UsageTabs'

export function ExecutionsToolbar({
  period,
  tab,
  filters,
  onPeriod,
  onTab,
  onFilters,
}: {
  period: Period
  tab: UsageTab
  filters: Filters
  onPeriod: (period: Period) => void
  onTab: (tab: UsageTab) => void
  onFilters: (filters: Filters) => void
}) {
  return (
    <div className="space-y-3">
      <DateRangeField period={period} onChange={onPeriod} />
      <UsageTabs value={tab} onChange={onTab} />
      <ExecutionFilters filters={filters} onChange={onFilters} />
    </div>
  )
}
