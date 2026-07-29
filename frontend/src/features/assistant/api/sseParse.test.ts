import { describe, expect, it } from 'vitest'
import { parseClientAction } from './sseParse'

describe('parseClientAction', () => {
  it('accepts allowlisted play and settings action shapes', () => {
    expect(
      parseClientAction({ type: 'play', path: '/read/book/chapter', label: 'Play' }),
    ).toEqual({ type: 'play', path: '/read/book/chapter', label: 'Play' })
    expect(
      parseClientAction({
        type: 'settings',
        label: 'Updated',
        settings: { theme: 'dark', font_size: 1.4 },
      }),
    ).toEqual({
      type: 'settings',
      label: 'Updated',
      settings: { theme: 'dark', font_size: 1.4 },
    })
  })

  it('accepts a validated download tracking action', () => {
    expect(
      parseClientAction({
        type: 'download',
        label: 'Audio download',
        job_id: 'job-1',
        book_id: 'book-1',
        chapter_from: 1,
        chapter_to: 5,
      }),
    ).toEqual({
      type: 'download',
      label: 'Audio download',
      jobId: 'job-1',
      bookId: 'book-1',
      chapterFrom: 1,
      chapterTo: 5,
    })
  })

  it('rejects unknown action types and external paths', () => {
    expect(parseClientAction({ type: 'script', path: '/', label: 'Run' })).toBeUndefined()
    expect(
      parseClientAction({ type: 'navigate', path: 'https://example.com', label: 'Open' }),
    ).toBeUndefined()
  })
})
