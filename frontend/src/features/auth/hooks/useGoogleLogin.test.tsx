import type { ReactNode } from 'react'
import { act, renderHook } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { meQueryKey } from './hooks'
import { useGoogleLogin } from './useGoogleLogin'

const navigateMock = vi.fn()
const fetchMeMock = vi.hoisted(() => vi.fn())

vi.mock('react-router', async (importOriginal) => {
  const actual = await importOriginal<typeof import('react-router')>()
  return { ...actual, useNavigate: () => navigateMock }
})

vi.mock('@/features/auth/api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/features/auth/api')>()
  return { ...actual, fetchMe: fetchMeMock }
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
    fetchMeMock.mockImplementation(() => Promise.reject(new Error('401')))
  })
  afterEach(() => {
    vi.restoreAllMocks()
    vi.useRealTimers()
    navigateMock.mockReset()
    fetchMeMock.mockReset()
  })

  it('starts idle, goes pending, then navigates to /reader on success', () => {
    mockOpen(fakePopup())
    const queryClient = new QueryClient()
    queryClient.setQueryData(['library', 'books'], [{ id: 'old' }])
    fetchMeMock.mockResolvedValue({ user: { id: 'u-new' } })
    const clearSpy = vi.spyOn(queryClient, 'clear')
    const fetchSpy = vi.spyOn(queryClient, 'fetchQuery')
    const view = renderUseGoogleLogin(queryClient)

    expect(view.result.current.state).toEqual({ status: 'idle' })

    act(() => view.result.current.start())
    expect(view.result.current.state).toEqual({ status: 'pending' })

    act(() => dispatchAuthMessage({ type: 'rtm-google-auth', ok: true, reason: null }))

    expect(navigateMock).toHaveBeenCalledWith('/reader', { replace: true })
    expect(clearSpy).toHaveBeenCalled()
    expect(queryClient.getQueryData(['library', 'books'])).toBeUndefined()
    expect(fetchSpy).toHaveBeenCalledWith(
      expect.objectContaining({ queryKey: meQueryKey }),
    )
  })

  it('clears the cached me error before navigating, so the guard shows loading', async () => {
    // Pins the fix for the invalidate+navigate race: a leftover 401 on `me`
    // would make ProtectedRoute bounce back to /login. We clear everything,
    // then start a fresh fetch so status is pending at navigate time.
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

    fetchMeMock.mockImplementation(
      () => new Promise(() => undefined), // stay pending through navigate
    )

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

  it('navigates when the popup reads closed but the session check confirms', async () => {
    // The COOP path: Google's Cross-Origin-Opener-Policy severs the opener, so
    // no postMessage arrives and popup.closed misreports true mid-flow. The
    // session cookie is still set; the hook must recover via /me.
    const popup = fakePopup()
    mockOpen(popup)
    fetchMeMock.mockImplementation(() => Promise.resolve({ user: { id: 'u1' } }))
    const view = renderUseGoogleLogin(new QueryClient())

    act(() => view.result.current.start())
    popup.closed = true
    await act(async () => {
      await vi.advanceTimersByTimeAsync(600)
    })

    expect(navigateMock).toHaveBeenCalledWith('/reader', { replace: true })
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
