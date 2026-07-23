import * as SheetPrimitive from '@radix-ui/react-dialog'
import { X } from 'lucide-react'
import type { ComponentPropsWithoutRef, HTMLAttributes } from 'react'
import { cn } from '@/shared/lib/cn'

export const Sheet = SheetPrimitive.Root
export const SheetTrigger = SheetPrimitive.Trigger
export const SheetClose = SheetPrimitive.Close

export function SheetContent({
  className,
  children,
  side = 'right',
  ...props
}: ComponentPropsWithoutRef<typeof SheetPrimitive.Content> & {
  side?: 'right' | 'left'
}) {
  return (
    <SheetPrimitive.Portal>
      <SheetPrimitive.Overlay className="fixed inset-0 z-[100] bg-black/50" />
      <SheetPrimitive.Content
        className={cn(
          'fixed inset-y-0 z-[100] flex w-full max-w-sm flex-col gap-4 overflow-y-auto border-border bg-background p-6 text-foreground shadow-xl',
          side === 'right' ? 'right-0 border-l' : 'left-0 border-r',
          className,
        )}
        {...props}
      >
        {children}
        <SheetPrimitive.Close className="absolute right-4 top-4 rounded-sm opacity-70 hover:opacity-100">
          <X className="h-4 w-4" />
          <span className="sr-only">Close</span>
        </SheetPrimitive.Close>
      </SheetPrimitive.Content>
    </SheetPrimitive.Portal>
  )
}

export function SheetHeader({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return <div className={cn('mb-2 flex flex-col gap-1.5 pr-8', className)} {...props} />
}

export function SheetTitle({
  className,
  ...props
}: ComponentPropsWithoutRef<typeof SheetPrimitive.Title>) {
  return (
    <SheetPrimitive.Title className={cn('text-lg font-semibold', className)} {...props} />
  )
}
