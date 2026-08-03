import { useState } from 'react'

/** limit/offset paging for the backend Page[T] envelope. */
export function usePageState(limit: number) {
  const [rawOffset, setRawOffset] = useState(0)
  const offset = Math.floor(rawOffset / limit) * limit

  return {
    limit,
    offset,
    prev: () => setRawOffset(Math.max(0, offset - limit)),
    next: (total: number) =>
      setRawOffset(offset + limit < total ? offset + limit : offset),
    reset: () => setRawOffset(0),
  }
}
