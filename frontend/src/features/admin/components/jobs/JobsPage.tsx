import { useState } from 'react'
import { useDownloadJobs, useScrapingJobs } from '@/features/admin/hooks/useAdminJobs'
import { usePageState } from '@/features/admin/hooks/usePageState'
import { useDataListLayout } from '@/shared/hooks/useDataListLayout'
import { DataListFrame, DataListPagination } from '@/shared/ui'
import type { JobsKind } from './JobsKindTabs'
import { JobsBody, JobsToolbar } from './JobsPageParts'

const ROW_REM = 2.5
const HEADER_REM = 2

export function JobsPage() {
  const layout = useDataListLayout({
    rowRem: ROW_REM,
    headerRem: HEADER_REM,
    fallback: 12,
  })
  const page = usePageState(layout.pageSize)
  const [kind, setKind] = useState<JobsKind>('scraping')
  const [status, setStatus] = useState('')
  const scraping = useScrapingJobs(status, page.limit, page.offset)
  const downloads = useDownloadJobs(status, page.limit, page.offset)
  const query = kind === 'scraping' ? scraping : downloads

  return (
    <DataListFrame
      sectionRef={layout.sectionRef}
      slotRef={layout.slotRef}
      title="Jobs monitor"
      description="Read-only view across all users. Cancel/retry live in the owning features."
      toolbar={
        <JobsToolbar
          kind={kind}
          status={status}
          onKind={(next) => {
            setKind(next)
            page.reset()
          }}
          onStatus={(next) => {
            setStatus(next)
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
      <JobsBody
        kind={kind}
        pageSize={layout.pageSize}
        scraping={scraping}
        downloads={downloads}
      />
    </DataListFrame>
  )
}
