import { DateRangeField } from '@/features/admin/components/common/DateRangeField'
import type { Period } from '@/features/admin/logic/period'
import { UsageTabs, type UsageTab } from './UsageTabs'

/** Shared title + date range + tab strip for both usage views. */
export function UsagePageHeader({
  period,
  onPeriod,
  tab,
  onTab,
}: {
  period: Period
  onPeriod: (period: Period) => void
  tab: UsageTab
  onTab: (tab: UsageTab) => void
}) {
  return (
    <div className="shrink-0 space-y-3">
      <div className="space-y-1">
        <h1 className="text-xl font-semibold tracking-tight">AI usage &amp; cost</h1>
        <p className="text-sm text-muted-foreground">
          Token, cost, and execution totals for the selected period.
        </p>
      </div>
      <DateRangeField period={period} onChange={onPeriod} />
      <UsageTabs value={tab} onChange={onTab} />
    </div>
  )
}
