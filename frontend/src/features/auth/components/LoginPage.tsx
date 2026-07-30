import { useGoogleLogin } from '@/features/auth/hooks'
import { GoogleButton } from './GoogleButton'

const ERROR_MESSAGES: Record<string, string> = {
  popup_blocked: 'Your browser blocked the sign-in window. Allow popups and try again.',
  popup_closed: 'The sign-in window was closed before finishing.',
  email_not_verified: 'This Google account has no verified email address.',
  google_denied: 'Google sign-in was cancelled.',
}
const FALLBACK_ERROR = 'Google sign-in failed. Please try again.'

export function LoginPage() {
  const { state, start } = useGoogleLogin()
  const errorMessage =
    state.status === 'error' ? (ERROR_MESSAGES[state.reason] ?? FALLBACK_ERROR) : null

  return (
    <div className="mx-auto flex min-h-screen max-w-sm flex-col justify-center px-4">
      <h1 className="mb-2 text-2xl font-semibold tracking-tight">Sign in to RTM</h1>
      <p className="mb-6 text-sm text-muted-foreground">
        Continue with your Google account.
      </p>
      <GoogleButton disabled={state.status === 'pending'} onClick={start} />
      {errorMessage ? (
        <p className="mt-4 text-sm text-destructive">{errorMessage}</p>
      ) : null}
    </div>
  )
}
