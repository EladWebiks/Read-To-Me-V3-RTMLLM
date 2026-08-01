import { PaginationControls } from '@/features/admin/components/common/PaginationControls'
import { useExecutions } from '@/features/admin/hooks/useUsage'
import { usePageState } from '@/features/admin/hooks/usePageState'
import type { Period } from '@/features/admin/logic/period'

export function ExecutionsTable({ period }: { period: Period }) {
  const page = usePageState(25)
  const { data } = useExecutions(period, page.limit, page.offset)
  if (!data) {
    return null
  }
  return (
    <div className="mt-4">
      <p className="mb-1 text-sm font-medium">Recent executions</p>
      <div className="overflow-x-auto">
        <table className="w-full text-left text-sm">
          <thead className="text-muted-foreground">
            <tr>
              <th className="px-2 py-1.5 font-medium">Time</th>
              <th className="px-2 py-1.5 font-medium">Task</th>
              <th className="px-2 py-1.5 font-medium">Model</th>
              <th className="px-2 py-1.5 font-medium">Tokens</th>
              <th className="px-2 py-1.5 font-medium">Cost</th>
              <th className="px-2 py-1.5 font-medium">Latency</th>
              <th className="px-2 py-1.5 font-medium">Status</th>
            </tr>
          </thead>
          <tbody>
            {data.items.map((row) => (
              <tr key={row.id} className="border-t border-border/60 tabular-nums">
                <td className="px-2 py-1.5">
                  {new Date(row.created_at).toLocaleString()}
                </td>
                <td className="px-2 py-1.5">{row.task}</td>
                <td className="px-2 py-1.5 font-mono text-xs">
                  {row.provider}/{row.model}
                </td>
                <td className="px-2 py-1.5">
                  {row.tokens_in}/{row.tokens_out}
                </td>
                <td className="px-2 py-1.5">${row.cost.toFixed(4)}</td>
                <td className="px-2 py-1.5">{row.latency_ms}ms</td>
                <td className="px-2 py-1.5">{row.status}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <PaginationControls
        total={data.total}
        limit={page.limit}
        offset={page.offset}
        onPrev={page.prev}
        onNext={() => page.next(data.total)}
      />
    </div>
  )
}
