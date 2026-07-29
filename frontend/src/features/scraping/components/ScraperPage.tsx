import { useRef, useState } from 'react'
import { Plus, Upload } from 'lucide-react'
import { Button } from '@/shared/ui'
import { useViewportLock } from '@/shared/hooks/useViewportLock'
import { useScrapeJobs } from '../hooks'
import { NewScrapeDialog } from './NewScrapeDialog'
import { ScrapeJobList } from './ScrapeJobList'
import { UploadEpubDialog } from './UploadEpubDialog'

export function ScraperPage() {
  const [open, setOpen] = useState(false)
  const [epubOpen, setEpubOpen] = useState(false)
  const sectionRef = useRef<HTMLDivElement>(null)
  useViewportLock(sectionRef)
  const jobs = useScrapeJobs()
  const busy = (jobs.data ?? []).some(
    (j) => j.status === 'pending' || j.status === 'running',
  )
  return (
    <div
      ref={sectionRef}
      className="mx-auto flex max-w-2xl flex-col gap-4 overflow-hidden animate-fade-in-up"
    >
      <div className="flex shrink-0 flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Scraper</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Scrape books from supported sites into your library, or upload an EPUB.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button
            type="button"
            variant="outline"
            className="gap-1.5"
            onClick={() => setEpubOpen(true)}
          >
            <Upload className="h-4 w-4" />
            Upload EPUB
          </Button>
          <Button type="button" disabled={busy} onClick={() => setOpen(true)}>
            <Plus className="h-4 w-4" />
            Add New Book
          </Button>
        </div>
      </div>
      <NewScrapeDialog open={open} onClose={() => setOpen(false)} />
      <UploadEpubDialog
        open={epubOpen}
        onClose={() => setEpubOpen(false)}
        onImported={() => void jobs.refetch()}
      />
      <ScrapeJobList />
    </div>
  )
}
