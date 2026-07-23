import { type FormEvent, useState } from 'react'
import { useNavigate } from 'react-router'
import { useLogin } from '@/features/auth/hooks'

export function LoginPage() {
  const navigate = useNavigate()
  const login = useLogin()
  const [username, setUsername] = useState('admin')
  const [password, setPassword] = useState('')

  function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    login.mutate(
      { username, password },
      {
        onSuccess: () => {
          void navigate('/reader', { replace: true })
        },
      },
    )
  }

  return (
    <div className="mx-auto flex min-h-screen max-w-sm flex-col justify-center px-4">
      <h1 className="mb-2 text-2xl font-semibold tracking-tight">Sign in to RTM</h1>
      <p className="mb-6 text-sm text-stone-600">Use the local admin account.</p>
      <LoginForm
        username={username}
        password={password}
        isPending={login.isPending}
        errorMessage={login.isError ? 'Invalid username or password.' : null}
        onUsernameChange={setUsername}
        onPasswordChange={setPassword}
        onSubmit={onSubmit}
      />
    </div>
  )
}

type LoginFormProps = {
  username: string
  password: string
  isPending: boolean
  errorMessage: string | null
  onUsernameChange: (value: string) => void
  onPasswordChange: (value: string) => void
  onSubmit: (event: FormEvent<HTMLFormElement>) => void
}

function LoginForm({
  username,
  password,
  isPending,
  errorMessage,
  onUsernameChange,
  onPasswordChange,
  onSubmit,
}: LoginFormProps) {
  return (
    <form className="space-y-4" onSubmit={onSubmit}>
      <label className="block text-sm">
        <span className="mb-1 block text-stone-700">Username</span>
        <input
          className="w-full rounded border border-stone-300 px-3 py-2"
          value={username}
          onChange={(event) => onUsernameChange(event.target.value)}
          autoComplete="username"
          required
        />
      </label>
      <label className="block text-sm">
        <span className="mb-1 block text-stone-700">Password</span>
        <input
          type="password"
          className="w-full rounded border border-stone-300 px-3 py-2"
          value={password}
          onChange={(event) => onPasswordChange(event.target.value)}
          autoComplete="current-password"
          required
        />
      </label>
      {errorMessage ? <p className="text-sm text-red-700">{errorMessage}</p> : null}
      <button
        type="submit"
        disabled={isPending}
        className="w-full rounded bg-stone-900 px-3 py-2 text-sm font-medium text-white disabled:opacity-60"
      >
        {isPending ? 'Signing in…' : 'Sign in'}
      </button>
    </form>
  )
}
