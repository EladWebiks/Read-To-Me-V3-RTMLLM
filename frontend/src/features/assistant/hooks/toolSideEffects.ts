import { booksQueryKey } from '@/features/library/hooks/bookHooks'
import { queryClient } from '@/shared/lib/queryClient'

const SCRAPE_TOOLS = new Set(['scrape_book_range'])

/** Refresh related pages when a chat tool mutates server state. */
export function applyToolSideEffects(toolName: string, ok: boolean): void {
  if (!ok) return
  if (SCRAPE_TOOLS.has(toolName)) {
    void queryClient.invalidateQueries({ queryKey: ['scraping', 'jobs'] })
    void queryClient.invalidateQueries({ queryKey: booksQueryKey })
  }
}
