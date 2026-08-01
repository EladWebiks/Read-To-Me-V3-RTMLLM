import { LoaderCircle } from 'lucide-react'
import { cn } from '@/shared/lib/cn'

const SIZES = { sm: 'size-3.5', md: 'size-5' }

/** The app's one spinner (the LiveStatusLine idiom, standardised). It keeps
 * spinning under reduced motion: it is the only signal that anything is
 * happening, and a small rotating icon is far less provocative than a
 * sweeping gradient — the skeleton shimmer is what gets disabled. */
export function Spinner({
  size = 'md',
  className,
}: {
  size?: 'sm' | 'md'
  className?: string
}) {
  return (
    <LoaderCircle
      aria-hidden="true"
      className={cn('animate-spin', SIZES[size], className)}
    />
  )
}

/** Spinner + muted label for small areas inside an already-rendered container,
 * where a skeleton would be more furniture than the content it stands in for. */
export function InlineLoader({ label }: { label: string }) {
  return (
    <span className="flex items-center gap-2 text-sm text-muted-foreground">
      <Spinner size="sm" />
      {label}
    </span>
  )
}
