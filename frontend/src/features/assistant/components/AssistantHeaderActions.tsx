import { Maximize2, MessageSquarePlus, Minimize2, X } from 'lucide-react'
import type { ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { Button, IconTooltip } from '@/shared/ui'
import { HistoryIconButton } from './HistoryIconButton'

export function AssistantHeaderActions({
  expanded,
  historyOpen = false,
  onOpenHistory,
  onNewChat,
  onToggleExpanded,
  onClose,
}: {
  expanded: boolean
  historyOpen?: boolean
  onOpenHistory: () => void
  onNewChat: () => void
  onToggleExpanded: () => void
  onClose: () => void
}) {
  const { t } = useTranslation('assistant')
  const fullscreenLabel = expanded ? t('header.exitFullscreen') : t('header.fullscreen')
  return (
    <div
      className="flex shrink-0 items-center gap-1"
      onPointerDown={(e) => e.stopPropagation()}
    >
      <Button
        type="button"
        variant="outline"
        size="sm"
        onClick={onNewChat}
        aria-label={t('history.newChat')}
        className="group/btn h-8 gap-1.5 rounded-full border-border/80 bg-background/70 px-2.5 text-xs font-medium shadow-sm transition-all duration-150 hover:bg-muted active:scale-[0.98]"
      >
        <MessageSquarePlus
          className="h-3.5 w-3.5 shrink-0 transition-transform duration-150 group-hover/btn:scale-110"
          strokeWidth={2.25}
          aria-hidden
        />
        <span className="whitespace-nowrap">{t('history.newChat')}</span>
      </Button>
      <HistoryIconButton pressed={historyOpen} onClick={onOpenHistory} />
      <IconTooltip label={fullscreenLabel}>
        <IconBtn label={fullscreenLabel} onClick={onToggleExpanded}>
          {expanded ? (
            <Minimize2 className="h-4 w-4 transition-transform duration-150 group-hover/btn:scale-110" />
          ) : (
            <Maximize2 className="h-4 w-4 transition-transform duration-150 group-hover/btn:scale-110" />
          )}
        </IconBtn>
      </IconTooltip>
      <IconTooltip label={t('header.close')}>
        <IconBtn label={t('closeAssistant')} onClick={onClose}>
          <X className="h-4 w-4 transition-transform duration-150 group-hover/btn:scale-110" />
        </IconBtn>
      </IconTooltip>
    </div>
  )
}

function IconBtn(props: {
  label: string
  onClick: () => void
  children: ReactNode
  disabled?: boolean
}) {
  return (
    <Button
      type="button"
      variant="ghost"
      size="icon"
      disabled={props.disabled}
      className="group/btn h-8 w-8 cursor-pointer transition-all duration-150 hover:bg-foreground/10 active:scale-95 disabled:pointer-events-none disabled:opacity-40"
      aria-label={props.label}
      onClick={props.onClick}
    >
      {props.children}
    </Button>
  )
}
