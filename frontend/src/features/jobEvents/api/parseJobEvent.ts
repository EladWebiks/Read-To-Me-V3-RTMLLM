import type { JobEvent } from './streamJobEvents'

export function parseJobEvent(raw: unknown): JobEvent | null {
  if (!raw || typeof raw !== 'object') return null
  const obj = raw as Record<string, unknown>
  if (obj.v !== 1) return null
  if (obj.kind !== 'scrape' && obj.kind !== 'download' && obj.kind !== 'import') {
    return null
  }
  if (typeof obj.job_id !== 'string' || typeof obj.status !== 'string') return null
  if (typeof obj.user_id !== 'string') return null
  return {
    v: 1,
    kind: obj.kind,
    job_id: obj.job_id,
    user_id: obj.user_id,
    status: obj.status,
    progress: parseProgress(obj.progress),
    book_id: typeof obj.book_id === 'string' ? obj.book_id : null,
    updated_at: typeof obj.updated_at === 'string' ? obj.updated_at : '',
  }
}

function parseProgress(raw: unknown): JobEvent['progress'] {
  if (!raw || typeof raw !== 'object') return null
  const obj = raw as Record<string, unknown>
  return {
    done: typeof obj.done === 'number' ? obj.done : null,
    total: typeof obj.total === 'number' ? obj.total : null,
  }
}
