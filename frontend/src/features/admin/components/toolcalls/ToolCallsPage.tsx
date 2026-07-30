import { useState } from 'react'
import type { ToolCallFilterValues } from '@/features/admin/api/toolCalls'
import { PaginationControls } from '@/features/admin/components/common/PaginationControls'
import { usePageState } from '@/features/admin/hooks/usePageState'
import { useToolCalls } from '@/features/admin/hooks/useToolCalls'
import { ToolCallFilters } from './ToolCallFilters'
import { ToolCallRow } from './ToolCallRow'

export function ToolCallsPage() {
  const [filters, setFilters] = useState<ToolCallFilterValues>({})
  const page = usePageState(25)
  const { data, isLoading, error } = useToolCalls(filters, page.limit, page.offset)

  const applyFilters = (next: ToolCallFilterValues) => {
    setFilters(next)
    page.reset()
  }

  if (isLoading) {
    return <p className="text-sm text-muted-foreground">Loading tool calls…</p>
  }
  if (error || !data) {
    return <p className="text-sm text-destructive">Failed to load tool calls.</p>
  }
  return (
    <section>
      <h1 className="mb-1 text-lg font-semibold">Tool-call audit</h1>
      <ToolCallFilters filters={filters} onChange={applyFilters} />
      <div className="space-y-2">
        {data.items.map((call) => (
          <ToolCallRow key={call.id} call={call} />
        ))}
        {data.items.length === 0 && (
          <p className="text-sm text-muted-foreground">
            No tool calls match the filters.
          </p>
        )}
      </div>
      <PaginationControls
        total={data.total}
        limit={page.limit}
        offset={page.offset}
        onPrev={page.prev}
        onNext={() => page.next(data.total)}
      />
    </section>
  )
}
