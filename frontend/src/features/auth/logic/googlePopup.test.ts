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

// jsdom has no BroadcastChannel; the stub below is also how tests simulate the
// COOP path where the callback page can only reach us through the channel.
class FakeBroadcastChannel {
  static instances: FakeBroadcastChannel[] = []
  onmessage: ((event: MessageEvent) => void) | null = null
  wasClosed = false
  name: string
  constructor(name: string) {
    this.name = name
    FakeBroadcastChannel.instances.push(this)
  }
  postMessage(): void {}
  close(): void {
    this.wasClosed = true
  }
}

function broadcastAuthMessage(data: unknown) {
  // A real closed channel delivers nothing; the fake must match.
  for (const channel of FakeBroadcastChannel.instances) {
    if (!channel.wasClosed) channel.onmessage?.(new MessageEvent('message', { data }))
  }
}

const noSession = () => Promise.resolve(false)

function startPopup(results: PopupResult[], checkSession = noSession) {
  return openGooglePopup('/api/auth/google/login', checkSession, (r) => results.push(r))
}

describe('openGooglePopup', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    FakeBroadcastChannel.instances = []
    vi.stubGlobal('BroadcastChannel', FakeBroadcastChannel)
  })
  afterEach(() => {
    vi.unstubAllGlobals()
    vi.restoreAllMocks()
    vi.useRealTimers()
  })

  it('reports success when the popup posts ok:true', () => {
    mockOpen(fakePopup())
    const results: PopupResult[] = []
    startPopup(results)
    dispatchAuthMessage({ type: 'rtm-google-auth', ok: true, reason: null })
    expect(results).toEqual([{ status: 'success' }])
  })

  it('reports the backend reason when ok:false', () => {
    mockOpen(fakePopup())
    const results: PopupResult[] = []
    startPopup(results)
    dispatchAuthMessage({ type: 'rtm-google-auth', ok: false, reason: 'state_mismatch' })
    expect(results).toEqual([{ status: 'error', reason: 'state_mismatch' }])
  })

  it('reports success from a BroadcastChannel message (COOP severs window.opener)', () => {
    // accounts.google.com sends Cross-Origin-Opener-Policy: same-origin, so the
    // callback page loads with window.opener === null and postMessage never
    // happens. The channel is the only signal that always arrives.
    mockOpen(fakePopup())
    const results: PopupResult[] = []
    startPopup(results)
    broadcastAuthMessage({ type: 'rtm-google-auth', ok: false, reason: 'google_denied' })
    expect(results).toEqual([{ status: 'error', reason: 'google_denied' }])
  })

  it('ignores messages from other origins and unrelated shapes', () => {
    mockOpen(fakePopup())
    const results: PopupResult[] = []
    startPopup(results)
    dispatchAuthMessage({ type: 'rtm-google-auth', ok: true }, 'https://evil.example')
    dispatchAuthMessage({ hello: 'world' })
    expect(results).toEqual([])
  })

  it('ignores malformed payloads on either channel', () => {
    mockOpen(fakePopup())
    const results: PopupResult[] = []
    startPopup(results)
    dispatchAuthMessage({ type: 'rtm-google-auth' })
    dispatchAuthMessage({ type: 'rtm-google-auth', ok: 'yes', reason: null })
    broadcastAuthMessage({ type: 'rtm-google-auth', ok: false, reason: { a: 1 } })
    expect(results).toEqual([])
  })

  it('reports popup_blocked when window.open returns null', () => {
    mockOpen(null)
    const results: PopupResult[] = []
    startPopup(results)
    expect(results).toEqual([{ status: 'error', reason: 'popup_blocked' }])
  })

  it('confirms the session instead of erroring when the popup reports closed', async () => {
    // COOP makes popup.closed read true the moment the popup reaches Google,
    // while the user is still signing in — it is NOT evidence of abandonment.
    const popup = fakePopup()
    mockOpen(popup)
    const results: PopupResult[] = []
    startPopup(results, () => Promise.resolve(true))
    popup.closed = true
    await vi.advanceTimersByTimeAsync(600)
    expect(results).toEqual([{ status: 'success' }])
  })

  it('keeps waiting while the session check says unauthenticated', async () => {
    const popup = fakePopup()
    mockOpen(popup)
    const results: PopupResult[] = []
    startPopup(results)
    popup.closed = true
    await vi.advanceTimersByTimeAsync(60_000)
    expect(results).toEqual([])
  })

  it('reports timeout once the flow deadline passes', async () => {
    const popup = fakePopup()
    mockOpen(popup)
    const results: PopupResult[] = []
    startPopup(results)
    popup.closed = true
    await vi.advanceTimersByTimeAsync(5 * 60_000 + 600)
    expect(results).toEqual([{ status: 'error', reason: 'timeout' }])
  })

  it('settles only once', async () => {
    const popup = fakePopup()
    mockOpen(popup)
    const results: PopupResult[] = []
    startPopup(results, () => Promise.resolve(true))
    dispatchAuthMessage({ type: 'rtm-google-auth', ok: true, reason: null })
    popup.closed = true
    await vi.advanceTimersByTimeAsync(600)
    expect(results).toHaveLength(1)
  })

  it('cleanup detaches listeners, clears the poll, and closes the channel', async () => {
    const popup = fakePopup()
    mockOpen(popup)
    const results: PopupResult[] = []
    const cleanup = startPopup(results, () => Promise.resolve(true))
    cleanup()
    dispatchAuthMessage({ type: 'rtm-google-auth', ok: true, reason: null })
    broadcastAuthMessage({ type: 'rtm-google-auth', ok: true, reason: null })
    popup.closed = true
    await vi.advanceTimersByTimeAsync(600)
    expect(results).toEqual([])
    expect(FakeBroadcastChannel.instances.every((c) => c.wasClosed)).toBe(true)
  })
})
