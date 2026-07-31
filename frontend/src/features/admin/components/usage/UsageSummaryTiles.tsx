import { StatTile } from '@/features/admin/components/common/StatTile'
import { useUsageOverview } from '@/features/admin/hooks/useUsage'
import type { Period } from '@/features/admin/logic/period'
import { BreakdownTable } from './BreakdownTable'

/** Quota rejections per kind over the selected period; hidden when none. */
function RejectionsByKind({ counts }: { counts: Record<string, number> }) {
  const kinds = Object.entries(counts)
  if (kinds.length === 0) {
    return null
  }
  return (
    <div className="mt-4 rounded-xl border p-3">
      <h3 className="mb-2 text-sm font-medium">Rejections by kind</h3>
      <table className="w-full text-sm">
        <tbody>
          {kinds.map(([kind, count]) => (
            <tr key={kind}>
              <td className="py-1 text-muted-foreground">{kind}</td>
              <td className="py-1 text-right tabular-nums">{count.toLocaleString()}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

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
        <StatTile label="Rejections" value={data.rejections.toLocaleString()} />
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
      <RejectionsByKind counts={data.rejections_by_kind} />
    </>
  )
}
