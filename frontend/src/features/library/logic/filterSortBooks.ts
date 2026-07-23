import type { Book, LibrarySort } from '../types'

export function filterAndSortBooks(
  books: Book[],
  query: string,
  sort: LibrarySort,
): Book[] {
  const q = query.toLowerCase().trim()
  const filtered = q
    ? books.filter(
        (b) => b.title.toLowerCase().includes(q) || b.author.toLowerCase().includes(q),
      )
    : [...books]
  return filtered.sort((a, b) => compareBooks(a, b, sort))
}

function compareBooks(a: Book, b: Book, sort: LibrarySort): number {
  if (sort === 'name') return a.title.localeCompare(b.title)
  if (sort === 'chapters') return b.chapter_count - a.chapter_count
  if (sort === 'added') {
    return new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
  }
  const aRead = a.last_read_at ? new Date(a.last_read_at).getTime() : 0
  const bRead = b.last_read_at ? new Date(b.last_read_at).getTime() : 0
  return bRead - aRead
}
