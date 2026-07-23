import type { LabelHTMLAttributes } from 'react'
import { cn } from '@/shared/lib/cn'

type Props = LabelHTMLAttributes<HTMLLabelElement>

export function Label({ className, ...props }: Props) {
  return (
    <label
      className={cn(
        'text-sm font-medium leading-none peer-disabled:cursor-not-allowed',
        className,
      )}
      {...props}
    />
  )
}
