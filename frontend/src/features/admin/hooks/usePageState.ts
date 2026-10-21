import { useState } from 'react'

/** limit/offset paging for the backend Page[T] envelope. */
export function usePageState(limit: number) {
  const [rawOffset, setRawOffset] = useState(0)
  const size = Math.max(1, limit)
  const offset = Math.floor(rawOffset / size) * size

  return {
    limit: size,
    offset,
    page: Math.floor(offset / size) + 1,
    prev: () => setRawOffset(Math.max(0, offset - size)),
    next: (total: number) => setRawOffset(offset + size < total ? offset + size : offset),
    setPage: (page: number) => setRawOffset(Math.max(0, page - 1) * size),
    reset: () => setRawOffset(0),
  }
}
