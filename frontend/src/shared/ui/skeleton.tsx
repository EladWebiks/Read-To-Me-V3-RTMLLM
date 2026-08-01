import { cn } from '@/shared/lib/cn'

/** Tinted loading block; all shape comes from className, so it composes into anything. */
export function Skeleton({ className }: { className?: string }) {
  return <div aria-hidden="true" className={cn('rtm-skeleton rounded-md', className)} />
}

/** Stacked prose-shaped bars; the last is 60% width so it reads as text, not a block. */
export function SkeletonText({ lines = 3 }: { lines?: number }) {
  return (
    <div aria-hidden="true" className="space-y-2">
      {Array.from({ length: lines }, (_, index) => (
        <Skeleton
          key={index}
          className={index === lines - 1 ? 'h-4 w-3/5' : 'h-4 w-full'}
        />
      ))}
    </div>
  )
}
