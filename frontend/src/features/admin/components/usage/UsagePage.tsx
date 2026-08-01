import { useState } from 'react'
import { DateRangeField } from '@/features/admin/components/common/DateRangeField'
import { defaultPeriod } from '@/features/admin/logic/period'
import { ByUserTable } from './ByUserTable'
import { ExecutionsTable } from './ExecutionsTable'
import { UsageSummaryTiles } from './UsageSummaryTiles'

export function UsagePage() {
  const [period, setPeriod] = useState(defaultPeriod)
  return (
    <section>
      <h1 className="mb-1 text-lg font-semibold">AI usage &amp; cost</h1>
      <DateRangeField period={period} onChange={setPeriod} />
      <UsageSummaryTiles period={period} />
      <ByUserTable period={period} />
      <ExecutionsTable period={period} />
    </section>
  )
}
