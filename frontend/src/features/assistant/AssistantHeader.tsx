import { Maximize2, MessageSquarePlus, Minimize2, X } from 'lucide-react'
import type { PointerEventHandler, ReactNode, RefObject } from 'react'
import { Button, IconTooltip } from '@/shared/ui'
import { useAssistantStore } from './assistantStore'

type Props = {
  expanded: boolean
  dragHandleProps?: { onPointerDown: PointerEventHandler }
  onToggleExpanded: () => void
  onClose: () => void
  titleRef?: RefObject<HTMLHeadingElement | null>
}

export function AssistantHeader(props: Props) {
  const { expanded, dragHandleProps, onToggleExpanded, onClose, titleRef } = props
  const requestNewChat = useAssistantStore((s) => s.requestNewChat)

  return (
    <header
      className={`flex shrink-0 items-center justify-between gap-2 border-b border-border/80 bg-card px-4 py-3 touch-none ${
        expanded ? '' : 'cursor-grab active:cursor-grabbing'
      }`}
      {...dragHandleProps}
    >
      <div className="min-w-0">
        <h2 ref={titleRef} tabIndex={-1} className="text-sm font-semibold outline-none">
          Assistant
        </h2>
        <p className="text-xs text-muted-foreground">
          {expanded ? 'Fullscreen · app-wide' : 'App-wide · Milestone B'}
        </p>
      </div>
      <div
        className="flex shrink-0 items-center gap-1"
        onPointerDown={(e) => e.stopPropagation()}
      >
        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={requestNewChat}
          aria-label="New chat"
          className="group/btn h-8 gap-1.5 rounded-full border-border/80 bg-background/70 px-2.5 text-xs font-medium shadow-sm transition-all duration-150 hover:bg-muted active:scale-[0.98]"
        >
          <MessageSquarePlus
            className="h-3.5 w-3.5 shrink-0 transition-transform duration-150 group-hover/btn:scale-110"
            strokeWidth={2.25}
            aria-hidden
          />
          <span className="whitespace-nowrap">New chat</span>
        </Button>
        <IconTooltip label={expanded ? 'Exit fullscreen' : 'Enter fullscreen'}>
          <IconBtn
            label={expanded ? 'Exit fullscreen' : 'Enter fullscreen'}
            onClick={onToggleExpanded}
          >
            {expanded ? (
              <Minimize2 className="h-4 w-4 transition-transform duration-150 group-hover/btn:scale-110" />
            ) : (
              <Maximize2 className="h-4 w-4 transition-transform duration-150 group-hover/btn:scale-110" />
            )}
          </IconBtn>
        </IconTooltip>
        <IconTooltip label="Close">
          <IconBtn label="Close assistant" onClick={onClose}>
            <X className="h-4 w-4 transition-transform duration-150 group-hover/btn:scale-110" />
          </IconBtn>
        </IconTooltip>
      </div>
    </header>
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
