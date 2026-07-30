export type GoogleAuthMessage = {
  type: 'rtm-google-auth'
  ok: boolean
  reason: string | null
}

// Validates every field the caller reads, not just `type`: the type predicate
// otherwise lets a same-origin message with a bogus shape (e.g. `ok: 'yes'`,
// `reason: {}`) through as a GoogleAuthMessage and settle the flow on it.
export function isGoogleAuthMessage(data: unknown): data is GoogleAuthMessage {
  if (typeof data !== 'object' || data === null) return false
  const message = data as { type?: unknown; ok?: unknown; reason?: unknown }
  return (
    message.type === 'rtm-google-auth' &&
    typeof message.ok === 'boolean' &&
    (message.reason === null || typeof message.reason === 'string')
  )
}
