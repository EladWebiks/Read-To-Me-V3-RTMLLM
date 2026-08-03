import type { ReactNode } from 'react'
import { act, renderHook } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { useAssistantStore } from '@/features/assistant/assistantStore'
import { useLogout } from './hooks'

const navigateMock = vi.fn()
const logoutMock = vi.hoisted(() => vi.fn())

vi.mock('react-router', async (importOriginal) => {
  const actual = await importOriginal<typeof import('react-router')>()
  return { ...actual, useNavigate: () => navigateMock }
})

vi.mock('@/features/auth/api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/features/auth/api')>()
  return { ...actual, logout: logoutMock }
})

function renderUseLogout(queryClient: QueryClient) {
  function wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  }
  return renderHook(() => useLogout(), { wrapper })
}

describe('useLogout', () => {
  beforeEach(() => {
    navigateMock.mockReset()
    logoutMock.mockReset()
    logoutMock.mockResolvedValue(undefined)
    useAssistantStore.setState({ conversationId: 'conv-1', newChatNonce: 0 })
  })

  it('clears all cached queries and the assistant thread on success', async () => {
    const queryClient = new QueryClient()
    queryClient.setQueryData(['library', 'books'], [{ id: 'book-a' }])
    const view = renderUseLogout(queryClient)

    await act(async () => {
      await view.result.current.mutateAsync()
    })

    expect(logoutMock).toHaveBeenCalled()
    expect(queryClient.getQueryData(['library', 'books'])).toBeUndefined()
    expect(useAssistantStore.getState().conversationId).toBeNull()
    expect(useAssistantStore.getState().newChatNonce).toBe(1)
    expect(navigateMock).toHaveBeenCalledWith('/login', { replace: true })
  })
})
