import { useState } from 'react'

/** limit/offset paging for the backend Page[T] envelope. */
export function usePageState(limit = 50) {
  const [offset, setOffset] = useState(0)
  return {
    limit,
    offset,
    prev: () => setOffset((current) => Math.max(0, current - limit)),
    next: (total: number) =>
      setOffset((current) => (current + limit < total ? current + limit : current)),
    reset: () => setOffset(0),
  }
}
