import type { Period } from '@/features/admin/logic/period'
import { ByUserTable } from './ByUserTable'
import { UsagePageHeader } from './UsagePageHeader'
import { UsageSummaryTiles } from './UsageSummaryTiles'
import type { UsageTab } from './UsageTabs'

export function UsageStatsPanel({
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
    <section className="space-y-4 animate-fade-in-up">
      <UsagePageHeader period={period} onPeriod={onPeriod} tab={tab} onTab={onTab} />
      <UsageSummaryTiles period={period} />
      <ByUserTable period={period} />
    </section>
  )
}
