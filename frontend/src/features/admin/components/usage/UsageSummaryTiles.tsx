import { StatTile } from '@/features/admin/components/common/StatTile'
import { useUsageOverview } from '@/features/admin/hooks/useUsage'
import type { Period } from '@/features/admin/logic/period'
import { BreakdownTable } from './BreakdownTable'

export function UsageSummaryTiles({ period }: { period: Period }) {
  const { data, isLoading } = useUsageOverview(period)
  if (isLoading || !data) {
    return <p className="text-sm text-muted-foreground">Loading usage…</p>
  }
  return (
    <>
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <StatTile label="Tokens in" value={data.tokens_in.toLocaleString()} />
        <StatTile label="Tokens out" value={data.tokens_out.toLocaleString()} />
        <StatTile label="Cost (USD)" value={`$${data.total_cost.toFixed(4)}`} />
        <StatTile label="Executions" value={data.execution_count.toLocaleString()} />
      </div>
      <div className="mt-4 grid gap-4 lg:grid-cols-2">
        <BreakdownTable
          title="By model"
          rows={data.by_model.map((row) => ({
            ...row,
            label: `${row.provider}/${row.model}`,
          }))}
        />
        <BreakdownTable
          title="By task"
          rows={data.by_task.map((row) => ({ ...row, label: row.task }))}
        />
      </div>
    </>
  )
}
