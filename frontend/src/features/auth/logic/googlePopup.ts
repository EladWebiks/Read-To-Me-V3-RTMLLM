import { isGoogleAuthMessage } from './googleAuthMessage'

export type PopupResult = { status: 'success' } | { status: 'error'; reason: string }

const RTM_AUTH_NAME = 'rtm-google-auth' // window + channel name; must match backend
const POPUP_FEATURES = 'width=500,height=600,popup=yes'
const POLL_MS = 500
const SESSION_CHECK_MS = 2000
const FLOW_TIMEOUT_MS = 5 * 60 * 1000

function openResultChannel(onAuthData: (data: unknown) => void): (() => void) | null {
  if (typeof BroadcastChannel === 'undefined') return null
  const channel = new BroadcastChannel(RTM_AUTH_NAME)
  channel.onmessage = (event) => onAuthData(event.data)
  return () => channel.close()
}

// Serializes /me probes: at most one in flight, success reported at most once.
function sessionProbe(checkSession: () => Promise<boolean>, onAuthed: () => void) {
  let inFlight = false
  return () => {
    if (inFlight) return
    inFlight = true
    checkSession().then(
      (authed) => {
        inFlight = false
        if (authed) onAuthed()
      },
      () => {
        inFlight = false
      },
    )
  }
}

// COOP context: accounts.google.com sends Cross-Origin-Opener-Policy:
// same-origin, severing the window pair once the popup reaches Google —
// `popup.closed` reads true while the window is still open and the callback
// loads with a null `window.opener`. So the result rides a same-origin
// BroadcastChannel (postMessage is a fallback) and a closed-looking popup is
// reconciled against the session via `checkSession`, never failed outright.
export function openGooglePopup(
  url: string,
  checkSession: () => Promise<boolean>,
  onResult: (result: PopupResult) => void,
): () => void {
  const popup = window.open(url, RTM_AUTH_NAME, POPUP_FEATURES)
  if (!popup) {
    onResult({ status: 'error', reason: 'popup_blocked' })
    return () => {}
  }
  let settled = false
  let elapsedMs = 0
  let sinceCheckMs = SESSION_CHECK_MS // first closed tick probes immediately
  const cleanup = () => {
    window.removeEventListener('message', onMessage)
    closeChannel?.()
    window.clearInterval(timer)
  }
  const settle = (result: PopupResult) => {
    if (settled) return
    settled = true
    cleanup()
    onResult(result)
  }
  const onAuthData = (data: unknown) => {
    if (!isGoogleAuthMessage(data)) return
    settle(
      data.ok
        ? { status: 'success' }
        : { status: 'error', reason: data.reason ?? 'unknown' },
    )
  }
  const onMessage = (event: MessageEvent) => {
    if (event.origin === window.location.origin) onAuthData(event.data)
  }
  const probe = sessionProbe(checkSession, () => settle({ status: 'success' }))
  const onTick = () => {
    elapsedMs += POLL_MS
    if (elapsedMs >= FLOW_TIMEOUT_MS) {
      settle({ status: 'error', reason: 'timeout' })
      return
    }
    if (!popup.closed) return
    sinceCheckMs += POLL_MS
    if (sinceCheckMs < SESSION_CHECK_MS) return
    sinceCheckMs = 0
    probe()
  }
  const timer = window.setInterval(onTick, POLL_MS)
  const closeChannel = openResultChannel(onAuthData)
  window.addEventListener('message', onMessage)
  return cleanup
}
