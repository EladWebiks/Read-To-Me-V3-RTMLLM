import { useState } from 'react'
import { defaultPeriod } from '@/features/admin/logic/period'
import { UsageExecutionsPanel } from './UsageExecutionsPanel'
import { UsageStatsPanel } from './UsageStatsPanel'
import type { UsageTab } from './UsageTabs'

export function UsagePage() {
  const [period, setPeriod] = useState(defaultPeriod)
  const [tab, setTab] = useState<UsageTab>('stats')

  if (tab === 'executions') {
    return (
      <UsageExecutionsPanel
        period={period}
        onPeriod={setPeriod}
        tab={tab}
        onTab={setTab}
      />
    )
  }

  return <UsageStatsPanel period={period} onPeriod={setPeriod} tab={tab} onTab={setTab} />
}
