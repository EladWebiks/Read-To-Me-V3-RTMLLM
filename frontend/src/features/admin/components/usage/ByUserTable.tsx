import type { UserUsage } from '@/features/admin/api/usage'
import { PaginationControls } from '@/features/admin/components/common/PaginationControls'
import { usePageState } from '@/features/admin/hooks/usePageState'
import { useUsageByUser } from '@/features/admin/hooks/useUsage'
import type { Period } from '@/features/admin/logic/period'

/** Monthly LLM quota for the row's tier; '—' = unlimited (no rule). */
function quotaLabel(row: UserUsage): string {
  const tokens =
    row.llm_tokens_limit === null ? '—' : row.llm_tokens_limit.toLocaleString()
  const cost = row.llm_cost_limit === null ? '—' : `$${row.llm_cost_limit.toFixed(2)}`
  return `${tokens} tok · ${cost}`
}

/** Non-LLM work this month: Audio chapters · Scraped chapters · EPUB imports. */
function jobsLabel(row: UserUsage): string {
  return `A:${row.month_audio_chapters} · S:${row.month_scrape_chapters} · I:${row.month_epub_imports}`
}

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
              <th className="px-2 py-1.5 font-medium">This month</th>
              <th className="px-2 py-1.5 font-medium">Quota</th>
              <th className="px-2 py-1.5 font-medium">Jobs (month)</th>
              <th className="px-2 py-1.5 font-medium">Rejections</th>
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
                <td className="px-2 py-1.5">
                  {row.month_tokens.toLocaleString()} tok · ${row.month_cost.toFixed(4)}
                </td>
                <td className="px-2 py-1.5">{quotaLabel(row)}</td>
                <td className="px-2 py-1.5">{jobsLabel(row)}</td>
                <td className="px-2 py-1.5">{row.period_rejections.toLocaleString()}</td>
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
        onPage={page.setPage}
      />
    </div>
  )
}
