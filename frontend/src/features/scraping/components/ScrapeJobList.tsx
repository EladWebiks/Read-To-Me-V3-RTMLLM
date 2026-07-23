import { useRef } from 'react'
import { ListPagination } from '@/shared/ui'
import { libraryBookHref } from '@/features/library/logic/libraryPaths'
import { ScrapeJobRow } from './ScrapeJobRow'
import { useScrapeJobListState } from './useScrapeJobListState'

export function ScrapeJobList() {
  const listSlotRef = useRef<HTMLDivElement>(null)
  const state = useScrapeJobListState(listSlotRef)
  return (
    <div className="flex min-h-0 flex-1 flex-col gap-3">
      <h2 className="shrink-0 text-sm font-medium text-muted-foreground">
        Recent jobs
        {state.showMocksHint ? ' (incl. layout mocks)' : ''}
      </h2>
      {state.isLoading ? <p className="text-sm text-muted-foreground">Loading…</p> : null}
      {state.items.length === 0 && !state.isLoading ? (
        <p className="text-sm text-muted-foreground">No scrape jobs yet.</p>
      ) : null}
      {state.items.length > 0 ? (
        <>
          <div ref={listSlotRef} className="min-h-0 flex-1 overflow-hidden">
            <ul className="space-y-2">
              {state.pageItems.map((job) => (
                <ScrapeJobRow
                  key={job.id}
                  job={job}
                  onCancel={() => state.onCancel(job)}
                  onOpenHref={
                    job.book_id && !job.id.startsWith('mock-')
                      ? libraryBookHref(job.book_id)
                      : null
                  }
                />
              ))}
            </ul>
          </div>
          <div className="shrink-0">
            <ListPagination
              page={state.page}
              pageCount={state.pageCount}
              total={state.items.length}
              pageSize={state.pageSize}
              onPage={state.setPage}
            />
          </div>
        </>
      ) : null}
    </div>
  )
}
