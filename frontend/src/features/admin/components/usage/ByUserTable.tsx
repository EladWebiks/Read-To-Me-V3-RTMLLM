import { PaginationControls } from '@/features/admin/components/common/PaginationControls'
import { usePageState } from '@/features/admin/hooks/usePageState'
import { useUsageByUser } from '@/features/admin/hooks/useUsage'
import type { Period } from '@/features/admin/logic/period'

export function ByUserTable({ period }: { period: Period }) {
  const page = usePageState(25)
  const { data } = useUsageByUser(period, page.limit, page.offset)
  if (!data) {
    return null
  }
  return (
    <div className="mt-4">
      <p className="mb-1 text-sm font-medium">By user</p>
      <div className="overflow-x-auto">
        <table className="w-full text-left text-sm">
          <thead className="text-muted-foreground">
            <tr>
              <th className="px-2 py-1.5 font-medium">User</th>
              <th className="px-2 py-1.5 font-medium">Tokens in</th>
              <th className="px-2 py-1.5 font-medium">Tokens out</th>
              <th className="px-2 py-1.5 font-medium">Cost</th>
              <th className="px-2 py-1.5 font-medium">Execs</th>
            </tr>
          </thead>
          <tbody>
            {data.items.map((row) => (
              <tr key={row.user_id} className="border-t border-border/60 tabular-nums">
                <td className="px-2 py-1.5">{row.username ?? row.user_id}</td>
                <td className="px-2 py-1.5">{row.tokens_in.toLocaleString()}</td>
                <td className="px-2 py-1.5">{row.tokens_out.toLocaleString()}</td>
                <td className="px-2 py-1.5">${row.total_cost.toFixed(4)}</td>
                <td className="px-2 py-1.5">{row.execution_count}</td>
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
