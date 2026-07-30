import type { ReactNode } from 'react'
import { act, renderHook } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { useGoogleLogin } from './useGoogleLogin'

const navigateMock = vi.fn()

vi.mock('react-router', async (importOriginal) => {
  const actual = await importOriginal<typeof import('react-router')>()
  return { ...actual, useNavigate: () => navigateMock }
})

type FakePopup = { closed: boolean }

function fakePopup(): FakePopup {
  return { closed: false }
}

function mockOpen(popup: FakePopup | null) {
  // Only `closed` is read by the implementation; strict TS needs the double cast.
  return vi.spyOn(window, 'open').mockReturnValue(popup as unknown as Window)
}

function dispatchAuthMessage(data: unknown, origin = window.location.origin) {
  window.dispatchEvent(new MessageEvent('message', { data, origin }))
}

function renderUseGoogleLogin(queryClient: QueryClient) {
  function wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  }
  return renderHook(() => useGoogleLogin(), { wrapper })
}

describe('useGoogleLogin', () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })
  afterEach(() => {
    vi.restoreAllMocks()
    vi.useRealTimers()
    navigateMock.mockReset()
  })

  it('starts idle, goes pending, then navigates to /reader on success', () => {
    mockOpen(fakePopup())
    const queryClient = new QueryClient()
    const invalidateSpy = vi.spyOn(queryClient, 'invalidateQueries')
    const view = renderUseGoogleLogin(queryClient)

    expect(view.result.current.state).toEqual({ status: 'idle' })

    act(() => view.result.current.start())
    expect(view.result.current.state).toEqual({ status: 'pending' })

    act(() => dispatchAuthMessage({ type: 'rtm-google-auth', ok: true, reason: null }))

    expect(navigateMock).toHaveBeenCalledWith('/reader', { replace: true })
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ['auth', 'me'] })
  })

  it('surfaces the backend reason as an error state', () => {
    mockOpen(fakePopup())
    const view = renderUseGoogleLogin(new QueryClient())

    act(() => view.result.current.start())
    act(() =>
      dispatchAuthMessage({
        type: 'rtm-google-auth',
        ok: false,
        reason: 'state_mismatch',
      }),
    )

    expect(view.result.current.state).toEqual({
      status: 'error',
      reason: 'state_mismatch',
    })
  })

  it('detaches the previous popup listener when start is called again', () => {
    mockOpen(fakePopup())
    const view = renderUseGoogleLogin(new QueryClient())

    act(() => view.result.current.start())
    act(() => view.result.current.start())
    act(() => dispatchAuthMessage({ type: 'rtm-google-auth', ok: true, reason: null }))

    expect(navigateMock).toHaveBeenCalledTimes(1)
  })

  it('cleans up the popup listener on unmount without throwing', () => {
    mockOpen(fakePopup())
    const view = renderUseGoogleLogin(new QueryClient())

    act(() => view.result.current.start())

    expect(() => view.unmount()).not.toThrow()

    act(() => dispatchAuthMessage({ type: 'rtm-google-auth', ok: true, reason: null }))
    expect(navigateMock).not.toHaveBeenCalled()
  })
})
