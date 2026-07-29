import { ArrowDown, ArrowUp, Trash2 } from 'lucide-react'
import { Button } from '@/shared/ui'

type Props = {
  index: number
  name: string
  importing: boolean
  isFirst: boolean
  isLast: boolean
  onRemove: (index: number) => void
  onMove: (index: number, direction: -1 | 1) => void
}

export function EpubFileRow(props: Props) {
  return (
    <div className="flex items-center gap-1.5 px-2 py-1">
      <span className="w-4 shrink-0 text-xs tabular-nums text-muted-foreground">
        {props.index + 1}
      </span>
      <span className="min-w-0 flex-1 truncate text-sm" title={props.name}>
        {props.name}
      </span>
      <Button
        type="button"
        variant="ghost"
        size="icon"
        className="size-6"
        disabled={props.importing || props.isFirst}
        onClick={() => props.onMove(props.index, -1)}
        aria-label="Move up"
      >
        <ArrowUp className="size-3.5" />
      </Button>
      <Button
        type="button"
        variant="ghost"
        size="icon"
        className="size-6"
        disabled={props.importing || props.isLast}
        onClick={() => props.onMove(props.index, 1)}
        aria-label="Move down"
      >
        <ArrowDown className="size-3.5" />
      </Button>
      <Button
        type="button"
        variant="ghost"
        size="icon"
        className="size-6 text-destructive"
        disabled={props.importing}
        onClick={() => props.onRemove(props.index)}
        aria-label="Remove"
      >
        <Trash2 className="size-3.5" />
      </Button>
    </div>
  )
}
