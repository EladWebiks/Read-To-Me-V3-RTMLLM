import { Maximize2, Minimize2, X } from 'lucide-react'
import type { PointerEventHandler, ReactNode, RefObject } from 'react'
import { Button, IconTooltip } from '@/shared/ui'

type Props = {
  expanded: boolean
  dragHandleProps?: { onPointerDown: PointerEventHandler }
  onToggleExpanded: () => void
  onClose: () => void
  titleRef?: RefObject<HTMLHeadingElement | null>
}

export function AssistantHeader(props: Props) {
  const { expanded, dragHandleProps, onToggleExpanded, onClose, titleRef } = props
  return (
    <header
      className={`flex shrink-0 items-center justify-between gap-2 border-b border-border/80 bg-card px-4 py-3 ${
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
        className="flex shrink-0 items-center gap-0.5"
        onPointerDown={(e) => e.stopPropagation()}
      >
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

function IconBtn(props: { label: string; onClick: () => void; children: ReactNode }) {
  return (
    <Button
      type="button"
      variant="ghost"
      size="icon"
      className="group/btn h-8 w-8 cursor-pointer transition-all duration-150 hover:bg-foreground/10 active:scale-95"
      aria-label={props.label}
      onClick={props.onClick}
    >
      {props.children}
    </Button>
  )
}
