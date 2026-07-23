import { useState } from 'react'
import { Plus } from 'lucide-react'
import { Button } from '@/shared/ui'
import { useScrapeJobs } from '../hooks'
import { NewScrapeDialog } from './NewScrapeDialog'
import { ScrapeJobList } from './ScrapeJobList'

export function ScraperPage() {
  const [open, setOpen] = useState(false)
  const jobs = useScrapeJobs()
  const busy = (jobs.data ?? []).some(
    (j) => j.status === 'pending' || j.status === 'running',
  )
  return (
    <div className="mx-auto max-w-2xl space-y-6 animate-fade-in-up">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Scraper</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Scrape books from supported sites into your library.
          </p>
        </div>
        <Button type="button" disabled={busy} onClick={() => setOpen(true)}>
          <Plus className="h-4 w-4" />
          Add New Book
        </Button>
      </div>
      <NewScrapeDialog open={open} onClose={() => setOpen(false)} />
      <ScrapeJobList />
    </div>
  )
}
