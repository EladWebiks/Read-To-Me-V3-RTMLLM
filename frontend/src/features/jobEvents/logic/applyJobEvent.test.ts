import { describe, expect, it, vi } from 'vitest'
import { applyJobEvent } from './applyJobEvent'
import type { JobEvent } from '../api/streamJobEvents'

function event(partial: Partial<JobEvent> & Pick<JobEvent, 'kind' | 'job_id'>): JobEvent {
  return {
    v: 1,
    user_id: 'u1',
    status: 'running',
    progress: null,
    book_id: null,
    updated_at: '',
    ...partial,
  }
}

describe('applyJobEvent', () => {
  it('invalidates scrape + library caches', () => {
    const invalidateQueries = vi.fn()
    applyJobEvent({ invalidateQueries } as never, event({ kind: 'scrape', job_id: 's1' }))
    expect(invalidateQueries).toHaveBeenCalled()
  })

  it('invalidates download list when book_id is present', () => {
    const invalidateQueries = vi.fn()
    applyJobEvent(
      { invalidateQueries } as never,
      event({ kind: 'download', job_id: 'd1', book_id: 'b1' }),
    )
    expect(invalidateQueries).toHaveBeenCalledWith({
      queryKey: ['downloads', 'list', 'b1'],
    })
  })
})
