import { LoaderCircle } from 'lucide-react'
import { useEffect, useState } from 'react'

/** Animated ephemeral status — reassures the user during long tool calls. */
export function LiveStatusLine({ label }: { label: string }) {
  const elapsed = useElapsed()
  const typedLabel = useTypedLabel(label)
  return (
    <div
      className="flex items-center gap-2 rounded-lg bg-muted/35 px-2.5 py-2 text-xs text-muted-foreground"
      aria-live="polite"
      role="status"
    >
      <LoaderCircle className="size-3.5 shrink-0 animate-spin" aria-hidden />
      <span dir="auto" className="sr-only">
        {label}
      </span>
      <span dir="auto" className="min-w-0 flex-1 truncate" aria-hidden>
        {typedLabel}
        <span className="assistant-status-caret" />
      </span>
      <span className="shrink-0 tabular-nums text-muted-foreground/70">
        {elapsed >= 2 ? `${elapsed}s` : ''}
      </span>
      <span className="flex gap-0.5" aria-hidden>
        {[0, 1, 2].map((index) => (
          <span
            key={index}
            className="size-1 animate-bounce rounded-full bg-current"
            style={{ animationDelay: `${index * 120}ms` }}
          />
        ))}
      </span>
    </div>
  )
}

function useTypedLabel(label: string): string {
  const [visible, setVisible] = useState('')
  useEffect(() => {
    let index = 0
    const timer = window.setInterval(() => {
      index += 1
      setVisible(label.slice(0, index))
      if (index >= label.length) window.clearInterval(timer)
    }, 18)
    return () => window.clearInterval(timer)
  }, [label])
  return visible
}

function useElapsed(): number {
  const [seconds, setSeconds] = useState(0)
  useEffect(() => {
    const started = Date.now()
    const timer = window.setInterval(
      () => setSeconds(Math.floor((Date.now() - started) / 1000)),
      1000,
    )
    return () => window.clearInterval(timer)
  }, [])
  return seconds
}
