import { History } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { Button } from '@/shared/ui'

export function HistoryIconButton({
  onClick,
  pressed = false,
}: {
  onClick: () => void
  pressed?: boolean
}) {
  const { t } = useTranslation('assistant')
  const label = pressed ? t('history.close') : t('history.title')
  return (
    <Button
      type="button"
      variant="outline"
      size="sm"
      aria-pressed={pressed}
      aria-label={label}
      onClick={onClick}
      className={
        pressed
          ? 'group/btn h-8 gap-1.5 rounded-full border-border bg-muted px-2.5 text-xs font-medium shadow-sm transition-all duration-150 active:scale-[0.98]'
          : 'group/btn h-8 gap-1.5 rounded-full border-border/80 bg-background/70 px-2.5 text-xs font-medium shadow-sm transition-all duration-150 hover:bg-muted active:scale-[0.98]'
      }
    >
      <History
        className="h-3.5 w-3.5 shrink-0 transition-transform duration-150 group-hover/btn:scale-110"
        strokeWidth={2.25}
        aria-hidden
      />
      <span className="whitespace-nowrap">{t('history.button')}</span>
    </Button>
  )
}
