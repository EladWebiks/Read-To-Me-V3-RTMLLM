import type { QueryClient } from '@tanstack/react-query'
import { useAssistantStore } from '@/features/assistant/assistantStore'

/**
 * Drop all cached server state and reset the assistant conversation when the
 * authenticated principal changes (logout or a successful Google login).
 *
 * Logout used to remove only `['auth','me']`, so library/usage caches flashed
 * the previous user after the next sign-in. The assistant also persisted
 * `conversationId` in localStorage across sessions.
 */
export function clearSessionClientState(queryClient: QueryClient): void {
  queryClient.clear()
  useAssistantStore.getState().requestNewChat()
}
