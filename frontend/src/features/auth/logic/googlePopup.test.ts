import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { openGooglePopup, type PopupResult } from './googlePopup'

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

describe('openGooglePopup', () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })
  afterEach(() => {
    vi.restoreAllMocks()
    vi.useRealTimers()
  })

  it('reports success when the popup posts ok:true', () => {
    mockOpen(fakePopup())
    const results: PopupResult[] = []
    openGooglePopup('/api/auth/google/login', (r) => results.push(r))
    dispatchAuthMessage({ type: 'rtm-google-auth', ok: true, reason: null })
    expect(results).toEqual([{ status: 'success' }])
  })

  it('reports the backend reason when ok:false', () => {
    mockOpen(fakePopup())
    const results: PopupResult[] = []
    openGooglePopup('/api/auth/google/login', (r) => results.push(r))
    dispatchAuthMessage({ type: 'rtm-google-auth', ok: false, reason: 'state_mismatch' })
    expect(results).toEqual([{ status: 'error', reason: 'state_mismatch' }])
  })

  it('ignores messages from other origins and unrelated shapes', () => {
    mockOpen(fakePopup())
    const results: PopupResult[] = []
    openGooglePopup('/api/auth/google/login', (r) => results.push(r))
    dispatchAuthMessage({ type: 'rtm-google-auth', ok: true }, 'https://evil.example')
    dispatchAuthMessage({ hello: 'world' })
    expect(results).toEqual([])
  })

  it('ignores same-origin messages whose ok/reason fields are malformed', () => {
    mockOpen(fakePopup())
    const results: PopupResult[] = []
    openGooglePopup('/api/auth/google/login', (r) => results.push(r))
    dispatchAuthMessage({ type: 'rtm-google-auth' })
    dispatchAuthMessage({ type: 'rtm-google-auth', ok: 'yes', reason: null })
    dispatchAuthMessage({ type: 'rtm-google-auth', ok: false, reason: { a: 1 } })
    expect(results).toEqual([])
  })

  it('reports popup_blocked when window.open returns null', () => {
    mockOpen(null)
    const results: PopupResult[] = []
    openGooglePopup('/api/auth/google/login', (r) => results.push(r))
    expect(results).toEqual([{ status: 'error', reason: 'popup_blocked' }])
  })

  it('reports popup_closed when the window closes without a message', () => {
    const popup = fakePopup()
    mockOpen(popup)
    const results: PopupResult[] = []
    openGooglePopup('/api/auth/google/login', (r) => results.push(r))
    popup.closed = true
    vi.advanceTimersByTime(600)
    expect(results).toEqual([{ status: 'error', reason: 'popup_closed' }])
  })

  it('settles only once', () => {
    const popup = fakePopup()
    mockOpen(popup)
    const results: PopupResult[] = []
    openGooglePopup('/api/auth/google/login', (r) => results.push(r))
    dispatchAuthMessage({ type: 'rtm-google-auth', ok: true, reason: null })
    popup.closed = true
    vi.advanceTimersByTime(600)
    expect(results).toHaveLength(1)
  })

  it('cleanup detaches the message listener and clears the poll interval', () => {
    const popup = fakePopup()
    mockOpen(popup)
    const results: PopupResult[] = []
    const cleanup = openGooglePopup('/api/auth/google/login', (r) => results.push(r))
    cleanup()
    dispatchAuthMessage({ type: 'rtm-google-auth', ok: true, reason: null })
    popup.closed = true
    vi.advanceTimersByTime(600)
    expect(results).toEqual([])
  })
})
