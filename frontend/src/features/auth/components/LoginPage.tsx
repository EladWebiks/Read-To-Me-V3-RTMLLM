import { useGoogleLogin } from '@/features/auth/hooks'
import { GoogleButton } from './GoogleButton'

const ERROR_MESSAGES: Record<string, string> = {
  popup_blocked: 'Your browser blocked the sign-in window. Allow popups and try again.',
  timeout: 'Google sign-in did not finish in time. Please try again.',
  email_not_verified: 'This Google account has no verified email address.',
  google_denied: 'Google sign-in was cancelled.',
  google_identity_conflict:
    'This account is already linked to a different Google account.',
}
const FALLBACK_ERROR = 'Google sign-in failed. Please try again.'

// Object.hasOwn, not `ERROR_MESSAGES[reason] ?? FALLBACK_ERROR`: a reason of
// "__proto__" resolves through the prototype chain to Object.prototype — a
// truthy non-string that defeats `??` and makes React throw when rendered.
function errorMessageFor(reason: string): string {
  return Object.hasOwn(ERROR_MESSAGES, reason) ? ERROR_MESSAGES[reason] : FALLBACK_ERROR
}

export function LoginPage() {
  const { state, start } = useGoogleLogin()
  const errorMessage = state.status === 'error' ? errorMessageFor(state.reason) : null

  return (
    <div className="mx-auto flex min-h-screen max-w-sm flex-col justify-center px-4">
      <h1 className="mb-2 text-2xl font-semibold tracking-tight">Sign in to RTM</h1>
      <p className="mb-6 text-sm text-muted-foreground">
        Continue with your Google account.
      </p>
      <GoogleButton disabled={state.status === 'pending'} onClick={start} />
      {/* A failed sign-in produces no other feedback, so the message must be
          announced. The live region is the always-mounted wrapper, not the
          conditional <p>: screen readers only announce changes *inside* a
          region that was already in the accessibility tree. */}
      <div aria-live="polite">
        {errorMessage ? (
          <p className="mt-4 text-sm text-destructive">{errorMessage}</p>
        ) : null}
      </div>
    </div>
  )
}
