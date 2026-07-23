/** Deep-link into the library chapters modal for a book. */
export function libraryBookHref(bookId: string): string {
  return `/library?book=${encodeURIComponent(bookId)}`
}
