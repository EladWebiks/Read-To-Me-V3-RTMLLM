import { LogOut, Moon, Sun } from 'lucide-react'
import { useTheme } from 'next-themes'
import { useLogout, useMe } from '@/features/auth/hooks'
import { AssistantNavButton } from '@/features/assistant'
import { SettingsSheet } from '@/features/settings/SettingsSheet'
import { Button } from '@/shared/ui'

export function ShellActions() {
  const { data } = useMe()
  const logout = useLogout()
  const { resolvedTheme, setTheme } = useTheme()
  const dark = resolvedTheme === 'dark'
  return (
    <>
      <AssistantNavButton />
      <Button
        type="button"
        variant="ghost"
        size="icon"
        className="cursor-pointer"
        aria-label="Toggle theme"
        onClick={() => setTheme(dark ? 'light' : 'dark')}
      >
        {dark ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
      </Button>
      <SettingsSheet />
      <span className="hidden text-sm text-muted-foreground sm:inline">
        {data?.user.username}
      </span>
      <Button
        type="button"
        variant="ghost"
        size="icon"
        className="cursor-pointer"
        aria-label="Log out"
        disabled={logout.isPending}
        onClick={() => logout.mutate()}
      >
        <LogOut className="h-4 w-4" />
      </Button>
    </>
  )
}
