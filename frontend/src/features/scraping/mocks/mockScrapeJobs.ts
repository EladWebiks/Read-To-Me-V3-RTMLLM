import type { ScrapeJob } from '../types'

/** Append mock jobs for layout / pagination preview (does not hide real jobs). */
export const SCRAPER_APPEND_MOCKS = false

const STATUSES = [
  'complete',
  'complete',
  'failed',
  'cancelled',
  'running',
  'pending',
] as const

/** Fake scrape jobs so multi-page layout can be verified. */
export const MOCK_SCRAPE_JOBS: ScrapeJob[] = Array.from({ length: 28 }, (_, index) => {
  const n = index + 1
  const status = STATUSES[index % STATUSES.length]!
  const chapters = 8 + ((index * 5) % 60)
  const day = String((index % 27) + 1).padStart(2, '0')
  const iso = `2026-07-${day}T10:00:00.000Z`
  const done = status === 'complete' ? chapters : Math.floor(chapters * 0.4)
  return {
    id: `mock-job-${String(n).padStart(2, '0')}`,
    book_id: status === 'complete' ? `mock-book-${String(n).padStart(2, '0')}` : null,
    book_title: `Mock Novel ${n}`,
    start_url: `https://example.com/novel/mock-${n}`,
    mode: index % 2 === 0 ? 'full' : 'range',
    chapter_from: index % 2 === 0 ? null : 1,
    chapter_to: index % 2 === 0 ? null : chapters,
    max_chapters: null,
    status,
    chapters_done: done,
    message:
      status === 'complete'
        ? `Finished. ${done} chapter(s) scraped.`
        : status === 'failed'
          ? 'Stopped after an error.'
          : status === 'running'
            ? `Scraping chapter ${done}…`
            : status === 'pending'
              ? 'Queued…'
              : 'Cancelled by user.',
    error: status === 'failed' ? 'Mock failure for layout preview.' : null,
    created_at: iso,
    updated_at: iso,
  }
})
