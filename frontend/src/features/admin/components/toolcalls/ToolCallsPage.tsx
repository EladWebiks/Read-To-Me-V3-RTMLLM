import { useState } from 'react'
import type { ToolCall, ToolCallFilterValues } from '@/features/admin/api/toolCalls'
import { usePageState } from '@/features/admin/hooks/usePageState'
import { useToolCalls } from '@/features/admin/hooks/useToolCalls'
import { useDataListLayout } from '@/shared/hooks/useDataListLayout'
import { DataListFrame, DataListPagination, QueryState, SkeletonTable } from '@/shared/ui'
import { ToolCallDetailsDialog } from './ToolCallDetailsDialog'
import { ToolCallFilters } from './ToolCallFilters'
import { ToolCallsDataTable } from './ToolCallsDataTable'

const ROW_REM = 2.5
const HEADER_REM = 2

export function ToolCallsPage() {
  const layout = useDataListLayout({
    rowRem: ROW_REM,
    headerRem: HEADER_REM,
    fallback: 12,
  })
  const page = usePageState(layout.pageSize)
  const [filters, setFilters] = useState<ToolCallFilterValues>({})
  const [selected, setSelected] = useState<ToolCall | null>(null)
  const query = useToolCalls(filters, page.limit, page.offset)

  return (
    <>
      <DataListFrame
        sectionRef={layout.sectionRef}
        slotRef={layout.slotRef}
        title="Tool-call audit"
        description="Cross-user tool executions with input/output payloads."
        toolbar={
          <ToolCallFilters
            filters={filters}
            onChange={(next) => {
              setFilters(next)
              page.reset()
            }}
          />
        }
        footer={
          query.data ? (
            <DataListPagination
              total={query.data.total}
              limit={page.limit}
              offset={page.offset}
              onPage={page.setPage}
            />
          ) : (
            <p className="text-sm text-muted-foreground">Measuring layout…</p>
          )
        }
      >
        <ToolCallsBody pageSize={layout.pageSize} query={query} onDetails={setSelected} />
      </DataListFrame>
      <ToolCallDetailsDialog
        call={selected}
        open={selected !== null}
        onOpenChange={(open) => {
          if (!open) setSelected(null)
        }}
      />
    </>
  )
}

function ToolCallsBody({
  pageSize,
  query,
  onDetails,
}: {
  pageSize: number
  query: ReturnType<typeof useToolCalls>
  onDetails: (call: ToolCall) => void
}) {
  return (
    <QueryState
      isPending={query.isLoading}
      isError={Boolean(query.error) || (!query.isLoading && !query.data)}
      loading={<SkeletonTable rows={Math.min(pageSize, 8)} cols={6} />}
      errorLabel="Couldn't load tool calls."
      label="Loading tool calls…"
      onRetry={() => void query.refetch()}
    >
      {query.data ? (
        <ToolCallsDataTable rows={query.data.items} onDetails={onDetails} />
      ) : null}
    </QueryState>
  )
}
