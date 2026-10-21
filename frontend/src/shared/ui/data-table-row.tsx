import type { ReactNode } from 'react'
import { cn } from '@/shared/lib/cn'

export function DataTableRow({
  children,
  className,
  muted,
}: {
  children: ReactNode
  className?: string
  muted?: boolean
}) {
  return (
    <tr
      className={cn(
        'border-t border-border/40 hover:bg-muted/25',
        muted && 'opacity-60',
        className,
      )}
    >
      {children}
    </tr>
  )
}
