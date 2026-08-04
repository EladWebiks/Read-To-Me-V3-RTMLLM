/** Truncate a history row title for the chat drawer. */
const TITLE_MAX = 72

export function truncateHistoryTitle(title: string | null | undefined): string {
  const cleaned = (title ?? '').trim() || 'Untitled chat'
  if (cleaned.length <= TITLE_MAX) return cleaned
  return `${cleaned.slice(0, TITLE_MAX - 1)}…`
}
