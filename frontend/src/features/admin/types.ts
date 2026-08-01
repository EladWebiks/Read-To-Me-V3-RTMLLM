/** Mirrors the backend Page[T] envelope (modules/admin/schemas.py). */
export type Page<T> = {
  items: T[]
  total: number
  limit: number
  offset: number
}
