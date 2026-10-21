import { useGoogleLogin } from '@/features/auth/hooks'
import { LoginActionColumn } from './LoginActionColumn'
import { LoginBrandPanel } from './LoginBrandPanel'

export function LoginPage() {
  const { state, start } = useGoogleLogin()
  const errorReason = state.status === 'error' ? state.reason : null

  return (
    <div className="flex min-h-dvh flex-col bg-background text-foreground lg:flex-row">
      <div className="shrink-0 lg:flex lg:h-dvh lg:w-[34rem] lg:shrink-0 lg:flex-col xl:w-[38rem]">
        <LoginBrandPanel />
      </div>
      <div
        className={
          'relative z-[1] -mt-5 flex flex-1 rounded-t-2xl bg-background ' +
          'shadow-[0_-12px_28px_rgba(12,10,9,0.28)] ' +
          'lg:mt-0 lg:min-h-dvh lg:rounded-none lg:border-l lg:border-border lg:shadow-none'
        }
      >
        <LoginActionColumn
          pending={state.status === 'pending'}
          errorReason={errorReason}
          onGoogle={start}
        />
      </div>
    </div>
  )
}
