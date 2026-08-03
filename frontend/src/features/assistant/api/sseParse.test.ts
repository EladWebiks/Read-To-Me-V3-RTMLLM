import { describe, expect, it } from 'vitest'
import { parseClientAction, parseConfirmation } from './sseParse'

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

describe('parseConfirmation', () => {
  it('parses action, title, and subtitle when present', () => {
    expect(
      parseConfirmation({
        call_id: 'c1',
        tool: 'scrape_book_range',
        risk: 'confirmation_required',
        summary: 'Scrape book: Foo',
        action: 'Scrape book',
        title: 'Foo',
        subtitle: 'novelfull',
        args: { url: 'https://x' },
        form: { fields: [] },
      }),
    ).toMatchObject({
      callId: 'c1',
      action: 'Scrape book',
      title: 'Foo',
      subtitle: 'novelfull',
      status: 'pending',
    })
  })

  it('omits blank presentation fields', () => {
    const parsed = parseConfirmation({
      call_id: 'c2',
      tool: 'create_audio_download',
      summary: 'Confirm',
      action: '  ',
      title: null,
    })
    expect(parsed.action).toBeUndefined()
    expect(parsed.title).toBeUndefined()
  })
})
