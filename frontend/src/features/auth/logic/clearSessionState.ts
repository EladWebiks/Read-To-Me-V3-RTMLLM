import type { QueryClient } from '@tanstack/react-query'
import { useAssistantStore } from '@/features/assistant/assistantStore'

/**
 * Drop all cached server state and reset assistant shell UI when the
 * authenticated principal changes (logout or a successful Google login).
 *
 * Logout used to remove only `['auth','me']`, so library/usage caches flashed
 * the previous user after the next sign-in. The assistant also kept an open
 * panel and `conversationId` in memory / localStorage across sessions.
 */
export function clearSessionClientState(queryClient: QueryClient): void {
  queryClient.clear()
  const assistant = useAssistantStore.getState()
  assistant.setOpen(false)
  assistant.requestNewChat()
}
