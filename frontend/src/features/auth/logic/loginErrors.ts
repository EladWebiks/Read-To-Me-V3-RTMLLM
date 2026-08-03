const ERROR_MESSAGES: Record<string, string> = {
  popup_blocked: 'Your browser blocked the sign-in window. Allow popups and try again.',
  timeout: 'Google sign-in did not finish in time. Please try again.',
  email_not_verified: 'This Google account has no verified email address.',
  google_denied: 'Google sign-in was cancelled.',
  google_identity_conflict:
    'This account is already linked to a different Google account.',
}
const FALLBACK_ERROR = 'Google sign-in failed. Please try again.'

export function errorMessageFor(reason: string): string {
  return Object.hasOwn(ERROR_MESSAGES, reason) ? ERROR_MESSAGES[reason] : FALLBACK_ERROR
}
