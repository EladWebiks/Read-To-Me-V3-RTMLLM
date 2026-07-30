import { LogOut, Moon, Sun } from 'lucide-react'
import { useTheme } from 'next-themes'
import { useLogout, useMe } from '@/features/auth/hooks'
import { AssistantNavButton } from '@/features/assistant'
import { SettingsSheet } from '@/features/settings/SettingsSheet'
import { Button, IconTooltip, TooltipProvider } from '@/shared/ui'
import { UserAvatar } from './UserAvatar'

export function ShellActions() {
  const { data } = useMe()
  const logout = useLogout()
  const { resolvedTheme, setTheme } = useTheme()
  const dark = resolvedTheme === 'dark'
  return (
    <TooltipProvider>
      <AssistantNavButton />
      <IconTooltip label={dark ? 'Light mode' : 'Dark mode'}>
        <Button
          type="button"
          variant="ghost"
          size="icon"
          className="cursor-pointer"
          aria-label={dark ? 'Switch to light mode' : 'Switch to dark mode'}
          onClick={() => setTheme(dark ? 'light' : 'dark')}
        >
          {dark ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
        </Button>
      </IconTooltip>
      <SettingsSheet />
      {data ? <UserAvatar user={data.user} /> : null}
      <IconTooltip label="Log out">
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
      </IconTooltip>
    </TooltipProvider>
  )
}
