import { GoogleButton } from './GoogleButton'
import { errorMessageFor } from '../logic/loginErrors'

type Props = {
  pending: boolean
  errorReason: string | null
  onGoogle: () => void
}

/** Action rail — Google now; register / premium can stack below later. */
export function LoginActionColumn(props: Props) {
  const errorMessage = props.errorReason ? errorMessageFor(props.errorReason) : null
  return (
    <section className="flex flex-1 flex-col justify-center px-6 py-10 sm:px-10 lg:px-14">
      <div className="mx-auto w-full max-w-sm animate-fade-in-up">
        <h1 className="text-2xl font-semibold tracking-tight text-foreground">Sign in</h1>
        <p className="mt-2 text-sm text-muted-foreground">
          Continue with your Google account to open your library.
        </p>
        <div className="mt-8 space-y-3">
          <GoogleButton disabled={props.pending} onClick={props.onGoogle} />
        </div>
        <div aria-live="polite" className="min-h-5">
          {errorMessage ? (
            <p className="mt-4 text-sm text-destructive">{errorMessage}</p>
          ) : null}
        </div>
        {/* Future: Create account · Buy Premium */}
      </div>
    </section>
  )
}
