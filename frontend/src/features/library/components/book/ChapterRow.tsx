import { useEffect, useRef } from 'react'
import { Button } from '@/shared/ui'
import type { ChapterSummary } from '@/features/library/types'

export function ChapterRow(props: {
  chapter: ChapterSummary
  isLastRead: boolean
  onPlay: () => void
  onEdit: () => void
  onDelete: () => void
}) {
  const ref = useRef<HTMLTableRowElement>(null)
  useEffect(() => {
    if (!props.isLastRead || !ref.current) return
    const node = ref.current
    const timer = window.setTimeout(() => {
      node.scrollIntoView({ block: 'center', behavior: 'smooth' })
    }, 120)
    return () => window.clearTimeout(timer)
  }, [props.isLastRead])

  return (
    <tr
      ref={ref}
      className={props.isLastRead ? 'bg-primary/10' : 'border-t border-border'}
    >
      <td className="px-3 py-2 tabular-nums">{props.chapter.chapter_number}</td>
      <td className="px-3 py-2">
        {props.chapter.title || `Chapter ${props.chapter.chapter_number}`}
        {props.isLastRead ? (
          <span className="ml-2 text-xs text-muted-foreground">(last read)</span>
        ) : null}
      </td>
      <td className="px-3 py-2">
        <div className="flex gap-1">
          <Button type="button" size="sm" variant="ghost" onClick={props.onPlay}>
            Play
          </Button>
          <Button type="button" size="sm" variant="ghost" onClick={props.onEdit}>
            Edit
          </Button>
          <Button
            type="button"
            size="sm"
            variant="ghost"
            className="text-destructive"
            onClick={props.onDelete}
          >
            Delete
          </Button>
        </div>
      </td>
    </tr>
  )
}
