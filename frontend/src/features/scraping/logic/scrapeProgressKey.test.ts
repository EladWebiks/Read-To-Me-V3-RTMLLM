import { describe, expect, it } from 'vitest'
import { scrapeProgressKey } from './scrapeProgressKey'
import type { ScrapeJob } from '../types'

function job(partial: Partial<ScrapeJob> & Pick<ScrapeJob, 'id'>): ScrapeJob {
  return {
    book_id: null,
    book_title: null,
    start_url: 'https://example.com',
    mode: 'full',
    chapter_from: null,
    chapter_to: null,
    max_chapters: null,
    status: 'running',
    chapters_done: 0,
    message: '',
    error: null,
    created_at: '',
    updated_at: '',
    ...partial,
  }
}

describe('scrapeProgressKey', () => {
  it('changes when chapters_done increases', () => {
    const a = scrapeProgressKey([job({ id: '1', chapters_done: 1 })])
    const b = scrapeProgressKey([job({ id: '1', chapters_done: 2 })])
    expect(a).not.toBe(b)
  })

  it('changes when status changes', () => {
    const a = scrapeProgressKey([job({ id: '1', status: 'running' })])
    const b = scrapeProgressKey([job({ id: '1', status: 'complete' })])
    expect(a).not.toBe(b)
  })
})
