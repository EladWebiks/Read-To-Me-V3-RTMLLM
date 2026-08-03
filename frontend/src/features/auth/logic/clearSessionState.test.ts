import { QueryClient } from '@tanstack/react-query'
import { beforeEach, describe, expect, it } from 'vitest'
import { useAssistantStore } from '@/features/assistant/assistantStore'
import { clearSessionClientState } from './clearSessionState'

describe('clearSessionClientState', () => {
  beforeEach(() => {
    useAssistantStore.setState({
      conversationId: 'conv-old',
      newChatNonce: 0,
      open: true,
      expanded: false,
      position: null,
    })
  })

  it('clears the react-query cache and starts a fresh assistant thread', () => {
    const queryClient = new QueryClient()
    queryClient.setQueryData(['library', 'books'], [{ id: 'book-a' }])
    queryClient.setQueryData(['auth', 'me'], { user: { id: 'u1' } })

    clearSessionClientState(queryClient)

    expect(queryClient.getQueryData(['library', 'books'])).toBeUndefined()
    expect(queryClient.getQueryData(['auth', 'me'])).toBeUndefined()
    expect(useAssistantStore.getState().conversationId).toBeNull()
    expect(useAssistantStore.getState().newChatNonce).toBe(1)
  })
})
