import type { SelectHTMLAttributes } from 'react'
import { cn } from '@/shared/lib/cn'

// Native <select size={n}> (visible row count) is shadowed by the variant
// name, exactly like Input. No call site uses it; the escape hatch is a raw
// <select>, not widening this type.
type Props = Omit<SelectHTMLAttributes<HTMLSelectElement>, 'size'> & {
  /** 'sm' is the compact inline-editor style (tables, filter bars). */
  size?: 'default' | 'sm'
}

const SIZES = {
  default:
    'h-9 w-full rounded-md border border-border bg-background px-3 py-1 text-sm shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50',
  sm: 'h-7 rounded border border-border bg-background px-1.5 py-0.5 text-xs focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50',
}

export function Select({ className, size = 'default', ...props }: Props) {
  return <select className={cn(SIZES[size], className)} {...props} />
}
