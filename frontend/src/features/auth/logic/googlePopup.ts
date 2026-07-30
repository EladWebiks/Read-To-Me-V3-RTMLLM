export type GoogleAuthMessage = {
  type: 'rtm-google-auth'
  ok: boolean
  reason: string | null
}

export type PopupResult = { status: 'success' } | { status: 'error'; reason: string }

const POPUP_NAME = 'rtm-google-auth'
const POPUP_FEATURES = 'width=500,height=600,popup=yes'
const CLOSED_POLL_MS = 500

function isGoogleAuthMessage(data: unknown): data is GoogleAuthMessage {
  return (
    typeof data === 'object' &&
    data !== null &&
    (data as { type?: unknown }).type === 'rtm-google-auth'
  )
}

export function openGooglePopup(
  url: string,
  onResult: (result: PopupResult) => void,
): () => void {
  const popup = window.open(url, POPUP_NAME, POPUP_FEATURES)
  if (!popup) {
    onResult({ status: 'error', reason: 'popup_blocked' })
    return () => {}
  }
  let settled = false
  const cleanup = () => {
    window.removeEventListener('message', onMessage)
    window.clearInterval(timer)
  }
  const settle = (result: PopupResult) => {
    if (settled) return
    settled = true
    cleanup()
    onResult(result)
  }
  const onMessage = (event: MessageEvent) => {
    if (event.origin !== window.location.origin) return
    if (!isGoogleAuthMessage(event.data)) return
    settle(
      event.data.ok
        ? { status: 'success' }
        : { status: 'error', reason: event.data.reason ?? 'unknown' },
    )
  }
  const timer = window.setInterval(() => {
    if (popup.closed) settle({ status: 'error', reason: 'popup_closed' })
  }, CLOSED_POLL_MS)
  window.addEventListener('message', onMessage)
  return cleanup
}
