import { useGoogleLogin } from '@/features/auth/hooks'
import { LoginActionColumn } from './LoginActionColumn'
import { LoginBrandPanel } from './LoginBrandPanel'

export function LoginPage() {
  const { state, start } = useGoogleLogin()
  const errorReason = state.status === 'error' ? state.reason : null

  return (
    <div className="flex min-h-dvh flex-col bg-background text-foreground lg:flex-row">
      <div className="lg:flex lg:w-[54%] lg:min-h-dvh lg:flex-col">
        <LoginBrandPanel />
      </div>
      <div className="flex flex-1 border-t border-border lg:min-h-dvh lg:border-l lg:border-t-0">
        <LoginActionColumn
          pending={state.status === 'pending'}
          errorReason={errorReason}
          onGoogle={start}
        />
      </div>
    </div>
  )
}
