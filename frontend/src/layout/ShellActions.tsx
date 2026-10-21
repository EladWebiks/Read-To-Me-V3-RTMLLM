import { LogOut, Moon, Sun } from 'lucide-react'
import { useTheme } from 'next-themes'
import { useTranslation } from 'react-i18next'
import { useLogout, useMe } from '@/features/auth/hooks'
import { AssistantNavButton } from '@/features/assistant'
import { SettingsSheet } from '@/features/settings/SettingsSheet'
import { Button, IconTooltip, TooltipProvider } from '@/shared/ui'
import { UserAvatar } from './UserAvatar'

export function ShellActions() {
  const { data } = useMe()
  const logout = useLogout()
  const { resolvedTheme, setTheme } = useTheme()
  const { t } = useTranslation('common')
  const dark = resolvedTheme === 'dark'
  return (
    <TooltipProvider>
      <AssistantNavButton />
      <IconTooltip label={dark ? t('shell.lightMode') : t('shell.darkMode')}>
        <Button
          type="button"
          variant="ghost"
          size="icon"
          className="cursor-pointer"
          aria-label={dark ? t('shell.switchToLight') : t('shell.switchToDark')}
          onClick={() => setTheme(dark ? 'light' : 'dark')}
        >
          {dark ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
        </Button>
      </IconTooltip>
      <SettingsSheet />
      {data ? (
        <UserAvatar user={data.user} membershipLabel={data.membership_label} />
      ) : null}
      <IconTooltip label={t('shell.logOut')}>
        <Button
          type="button"
          variant="ghost"
          size="icon"
          className="cursor-pointer"
          aria-label={t('shell.logOut')}
          disabled={logout.isPending}
          onClick={() => logout.mutate()}
        >
          <LogOut className="h-4 w-4" />
        </Button>
      </IconTooltip>
    </TooltipProvider>
  )
}
