import * as TooltipPrimitive from '@radix-ui/react-tooltip'
import type { ComponentPropsWithoutRef, ReactElement } from 'react'
import { cn } from '@/shared/lib/cn'

export function TooltipProvider({
  children,
  delayDuration = 350,
  skipDelayDuration = 200,
  ...props
}: ComponentPropsWithoutRef<typeof TooltipPrimitive.Provider>) {
  return (
    <TooltipPrimitive.Provider
      delayDuration={delayDuration}
      skipDelayDuration={skipDelayDuration}
      {...props}
    >
      {children}
    </TooltipPrimitive.Provider>
  )
}

export const Tooltip = TooltipPrimitive.Root
export const TooltipTrigger = TooltipPrimitive.Trigger

export function TooltipContent({
  className,
  sideOffset = 8,
  children,
  ...props
}: ComponentPropsWithoutRef<typeof TooltipPrimitive.Content>) {
  return (
    <TooltipPrimitive.Portal>
      <TooltipPrimitive.Content
        sideOffset={sideOffset}
        className={cn(
          'z-[200] select-none rounded-lg border border-border/70 bg-card/95 px-2.5 py-1.5',
          'text-[11px] font-medium tracking-wide text-foreground shadow-lg shadow-black/10',
          'backdrop-blur-md will-change-[transform,opacity]',
          'data-[state=delayed-open]:animate-[rtm-tooltip-in_150ms_cubic-bezier(0.16,1,0.3,1)_both]',
          'data-[state=instant-open]:animate-[rtm-tooltip-in_120ms_ease-out_both]',
          'data-[state=closed]:animate-[rtm-tooltip-out_100ms_ease-in_both]',
          className,
        )}
        {...props}
      >
        {children}
        <TooltipPrimitive.Arrow
          className="fill-card drop-shadow-sm"
          width={11}
          height={6}
        />
      </TooltipPrimitive.Content>
    </TooltipPrimitive.Portal>
  )
}

/** Convenience wrapper for icon buttons in the shell. */
export function IconTooltip(props: {
  label: string
  children: ReactElement
  side?: 'top' | 'bottom' | 'left' | 'right'
}) {
  return (
    <Tooltip>
      <TooltipTrigger asChild>{props.children}</TooltipTrigger>
      <TooltipContent side={props.side ?? 'bottom'}>{props.label}</TooltipContent>
    </Tooltip>
  )
}
