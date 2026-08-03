import * as SliderPrimitive from '@radix-ui/react-slider'
import type { ComponentPropsWithoutRef } from 'react'
import { cn } from '@/shared/lib/cn'

type SliderProps = Omit<
  ComponentPropsWithoutRef<typeof SliderPrimitive.Root>,
  'value' | 'onValueChange' | 'defaultValue'
> & {
  value: number
  onValueChange: (value: number) => void
}

/** Single-thumb range control styled for reader/settings surfaces. */
export function Slider({ className, value, onValueChange, ...props }: SliderProps) {
  return (
    <SliderPrimitive.Root
      className={cn(
        'relative flex w-full touch-none select-none items-center py-1',
        className,
      )}
      value={[value]}
      onValueChange={(next) => onValueChange(next[0] ?? value)}
      {...props}
    >
      <SliderPrimitive.Track className="relative h-1 w-full grow overflow-hidden rounded-full bg-muted-foreground/25">
        <SliderPrimitive.Range className="absolute h-full rounded-full bg-foreground/70" />
      </SliderPrimitive.Track>
      <SliderPrimitive.Thumb
        className={cn(
          'block h-3.5 w-3.5 rounded-full border border-border bg-background shadow-sm',
          'transition-[box-shadow,transform] duration-150',
          'hover:scale-110 focus-visible:outline-none focus-visible:ring-2',
          'focus-visible:ring-ring disabled:pointer-events-none disabled:opacity-50',
        )}
      />
    </SliderPrimitive.Root>
  )
}
