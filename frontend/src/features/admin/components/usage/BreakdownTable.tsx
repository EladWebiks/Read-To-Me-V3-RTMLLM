import type { UsageBreakdown } from '@/features/admin/api/usage'

type Row = UsageBreakdown & { label: string }

export function BreakdownTable({ title, rows }: { title: string; rows: Row[] }) {
  return (
    <div className="overflow-x-auto rounded-lg border border-border/70">
      <p className="border-b border-border/60 px-3 py-1.5 text-sm font-medium">{title}</p>
      <table className="w-full text-left text-sm">
        <thead className="text-muted-foreground">
          <tr>
            <th className="px-3 py-1.5 font-medium">Bucket</th>
            <th className="px-3 py-1.5 font-medium">In</th>
            <th className="px-3 py-1.5 font-medium">Out</th>
            <th className="px-3 py-1.5 font-medium">Cost</th>
            <th className="px-3 py-1.5 font-medium">Execs</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.label} className="border-t border-border/50 tabular-nums">
              <td className="px-3 py-1.5 font-mono text-xs">{row.label}</td>
              <td className="px-3 py-1.5">{row.tokens_in.toLocaleString()}</td>
              <td className="px-3 py-1.5">{row.tokens_out.toLocaleString()}</td>
              <td className="px-3 py-1.5">${row.total_cost.toFixed(4)}</td>
              <td className="px-3 py-1.5">{row.execution_count}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
