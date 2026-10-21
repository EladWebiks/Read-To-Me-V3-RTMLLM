import { useState } from 'react'
import type { ExecutionFilters as Filters } from '@/features/admin/api/usage'
import { usePageState } from '@/features/admin/hooks/usePageState'
import { useExecutions } from '@/features/admin/hooks/useUsage'
import type { Period } from '@/features/admin/logic/period'
import { useDataListLayout } from '@/shared/hooks/useDataListLayout'
import { DataListFrame, DataListPagination, QueryState, SkeletonTable } from '@/shared/ui'
import { ExecutionsDataTable } from './ExecutionsDataTable'
import { ExecutionsToolbar } from './ExecutionsToolbar'
import type { UsageTab } from './UsageTabs'

const ROW_REM = 2.25
const HEADER_REM = 2

export function UsageExecutionsPanel({
  period,
  onPeriod,
  tab,
  onTab,
}: {
  period: Period
  onPeriod: (period: Period) => void
  tab: UsageTab
  onTab: (tab: UsageTab) => void
}) {
  const layout = useDataListLayout({
    rowRem: ROW_REM,
    headerRem: HEADER_REM,
    fallback: 12,
  })
  const page = usePageState(layout.pageSize)
  const [filters, setFilters] = useState<Filters>({})
  const query = useExecutions(period, page.limit, page.offset, filters)

  return (
    <DataListFrame
      sectionRef={layout.sectionRef}
      slotRef={layout.slotRef}
      title="AI usage & cost"
      description="Token, cost, and execution totals for the selected period."
      toolbar={
        <ExecutionsToolbar
          period={period}
          tab={tab}
          filters={filters}
          onPeriod={(next) => {
            onPeriod(next)
            page.reset()
          }}
          onTab={onTab}
          onFilters={(next) => {
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
      <ExecutionsBody pageSize={layout.pageSize} query={query} />
    </DataListFrame>
  )
}

function ExecutionsBody({
  pageSize,
  query,
}: {
  pageSize: number
  query: ReturnType<typeof useExecutions>
}) {
  return (
    <QueryState
      isPending={query.isLoading}
      isError={Boolean(query.error) || (!query.isLoading && !query.data)}
      loading={<SkeletonTable rows={Math.min(pageSize, 8)} cols={7} />}
      errorLabel="Couldn't load executions."
      label="Loading executions…"
      onRetry={() => void query.refetch()}
    >
      {query.data ? <ExecutionsDataTable rows={query.data.items} /> : null}
    </QueryState>
  )
}
