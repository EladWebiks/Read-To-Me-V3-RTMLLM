import type { ReactNode } from 'react'
import { act, renderHook } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { meQueryKey } from './hooks'
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
    const resetSpy = vi.spyOn(queryClient, 'resetQueries')
    const view = renderUseGoogleLogin(queryClient)

    expect(view.result.current.state).toEqual({ status: 'idle' })

    act(() => view.result.current.start())
    expect(view.result.current.state).toEqual({ status: 'pending' })

    act(() => dispatchAuthMessage({ type: 'rtm-google-auth', ok: true, reason: null }))

    expect(navigateMock).toHaveBeenCalledWith('/reader', { replace: true })
    expect(resetSpy).toHaveBeenCalledWith({ queryKey: meQueryKey })
  })

  it('clears the cached me error before navigating, so the guard shows loading', async () => {
    // Pins the fix for the invalidate+navigate race: with invalidateQueries the
    // cached 401 error survives the navigate, ProtectedRoute reads
    // isLoading === false / isError === true and bounces back to /login.
    mockOpen(fakePopup())
    const queryClient = new QueryClient()
    await queryClient
      .fetchQuery({
        queryKey: meQueryKey,
        queryFn: () => Promise.reject(new Error('401')),
        retry: false,
      })
      .catch(() => undefined)
    expect(queryClient.getQueryState(meQueryKey)?.status).toBe('error')

    let statusAtNavigate: string | undefined
    navigateMock.mockImplementation(() => {
      statusAtNavigate = queryClient.getQueryState(meQueryKey)?.status
    })

    const view = renderUseGoogleLogin(queryClient)
    act(() => view.result.current.start())
    act(() => dispatchAuthMessage({ type: 'rtm-google-auth', ok: true, reason: null }))

    expect(navigateMock).toHaveBeenCalledWith('/reader', { replace: true })
    expect(statusAtNavigate).toBe('pending')
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
