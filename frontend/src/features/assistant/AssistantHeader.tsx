import type { PointerEventHandler, RefObject } from 'react'
import { useTranslation } from 'react-i18next'
import { AssistantHeaderActions } from './components/AssistantHeaderActions'

type Props = {
  expanded: boolean
  dragHandleProps?: { onPointerDown: PointerEventHandler }
  onToggleExpanded: () => void
  onClose: () => void
  historyOpen?: boolean
  onOpenHistory: () => void
  onNewChat: () => void
  titleRef?: RefObject<HTMLHeadingElement | null>
}

export function AssistantHeader({
  expanded,
  dragHandleProps,
  onToggleExpanded,
  onClose,
  historyOpen = false,
  onOpenHistory,
  onNewChat,
  titleRef,
}: Props) {
  const { t } = useTranslation('assistant')
  return (
    <header
      className={`flex shrink-0 items-center justify-between gap-2 border-b border-border/80 bg-card px-4 py-3 touch-none ${
        expanded ? '' : 'cursor-grab active:cursor-grabbing'
      }`}
      {...dragHandleProps}
    >
      <div className="min-w-0">
        <h2 ref={titleRef} tabIndex={-1} className="text-sm font-semibold outline-none">
          {t('title')}
        </h2>
        <p className="text-xs text-muted-foreground">
          {expanded ? t('subtitleFullscreen') : t('subtitle')}
        </p>
      </div>
      <AssistantHeaderActions
        expanded={expanded}
        historyOpen={historyOpen}
        onOpenHistory={onOpenHistory}
        onNewChat={onNewChat}
        onToggleExpanded={onToggleExpanded}
        onClose={onClose}
      />
    </header>
  )
}
