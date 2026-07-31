import { type FormEvent, useState } from 'react'
import { ApiError } from '@/shared/lib/api'
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/shared/ui'
import { useCreateScrapeJob } from '../hooks'
import { ScrapeDialogActions } from './ScrapeDialogActions'
import { ScrapeDialogFields } from './ScrapeDialogFields'

type Props = { open: boolean; onClose: () => void }

/** Show the server's own copy (quota 429s, unsupported source) when we have it. */
function scrapeErrorMessage(error: unknown): string | null {
  if (error === null) return null
  if (error instanceof ApiError) return error.message
  return 'Could not start scrape — check the URL.'
}

export function NewScrapeDialog({ open, onClose }: Props) {
  const form = useScrapeForm(onClose)
  return (
    <Dialog open={open} onOpenChange={(next) => form.handleOpenChange(next)}>
      <DialogContent>
        <form onSubmit={form.onSubmit} className="space-y-4">
          <DialogHeader>
            <DialogTitle>Scrape New Book</DialogTitle>
          </DialogHeader>
          <ScrapeDialogFields {...form.fields} />
          {form.error ? <p className="text-sm text-destructive">{form.error}</p> : null}
          <ScrapeDialogActions
            pending={form.pending}
            canSubmit={form.canSubmit}
            onCancel={form.cancel}
          />
        </form>
      </DialogContent>
    </Dialog>
  )
}

function useScrapeForm(onClose: () => void) {
  const create = useCreateScrapeJob()
  const [url, setUrl] = useState('')
  const [bookUrl, setBookUrl] = useState('')
  const [maxChapters, setMaxChapters] = useState('')
  const [startingChapter, setStartingChapter] = useState('')
  const reset = () => {
    setUrl('')
    setBookUrl('')
    setMaxChapters('')
    setStartingChapter('')
  }
  const cancel = () => {
    reset()
    onClose()
  }
  return {
    pending: create.isPending,
    error: scrapeErrorMessage(create.error),
    canSubmit: Boolean(url.trim()),
    fields: {
      url,
      setUrl,
      bookUrl,
      setBookUrl,
      maxChapters,
      setMaxChapters,
      startingChapter,
      setStartingChapter,
    },
    cancel,
    handleOpenChange: (next: boolean) => {
      if (!next && !create.isPending) cancel()
    },
    onSubmit: (event: FormEvent) => {
      event.preventDefault()
      if (!url.trim()) return
      void create
        .mutateAsync({
          url: url.trim(),
          book_url: bookUrl.trim() || null,
          max_chapters: maxChapters ? Number(maxChapters) : null,
          starting_chapter: startingChapter ? Number(startingChapter) : null,
        })
        .then(cancel)
    },
  }
}
