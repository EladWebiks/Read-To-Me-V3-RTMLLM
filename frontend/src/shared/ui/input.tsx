import type { InputHTMLAttributes } from 'react'
import { cn } from '@/shared/lib/cn'

type Props = Omit<InputHTMLAttributes<HTMLInputElement>, 'size'> & {
  /** 'sm' is the compact inline-editor style (tables, in-row editors). */
  size?: 'default' | 'sm'
}

const SIZES = {
  default:
    'flex h-9 w-full rounded-md border border-border bg-background px-3 py-1 text-sm shadow-sm transition-colors placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50',
  sm: 'h-7 rounded border border-border bg-background px-1.5 py-0.5 text-xs placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50',
}

export function Input({ className, type = 'text', size = 'default', ...props }: Props) {
  return <input type={type} className={cn(SIZES[size], className)} {...props} />
}
