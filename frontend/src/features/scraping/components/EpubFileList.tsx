import { Plus } from 'lucide-react'
import { Button } from '@/shared/ui'
import { EpubFileRow } from './EpubFileRow'

type Props = {
  files: File[]
  importing: boolean
  onAddClick: () => void
  onClear: () => void
  onRemove: (index: number) => void
  onMove: (index: number, direction: -1 | 1) => void
}

export function EpubFileList(props: Props) {
  const total = props.files.reduce((sum, f) => sum + f.size, 0)
  return (
    <div className="space-y-2">
      <p className="text-xs text-muted-foreground">
        Add parts in reading order — they merge into one book.
      </p>
      <Toolbar {...props} total={total} />
      {props.files.length > 0 ? (
        <div className="max-h-36 divide-y divide-border overflow-y-auto rounded-md border border-border">
          {props.files.map((file, i) => (
            <EpubFileRow
              key={`${file.name}-${file.lastModified}-${i}`}
              index={i}
              name={file.name}
              importing={props.importing}
              isFirst={i === 0}
              isLast={i === props.files.length - 1}
              onRemove={props.onRemove}
              onMove={props.onMove}
            />
          ))}
        </div>
      ) : (
        <button
          type="button"
          onClick={props.onAddClick}
          disabled={props.importing}
          className="flex w-full items-center justify-center rounded-md border border-dashed border-border px-3 py-6 text-sm text-muted-foreground hover:bg-muted/40 disabled:opacity-50"
        >
          Choose an .epub file
        </button>
      )}
    </div>
  )
}

function Toolbar(props: Props & { total: number }) {
  return (
    <div className="flex items-center gap-2">
      <Button
        type="button"
        variant="outline"
        size="sm"
        className="gap-1.5"
        onClick={props.onAddClick}
        disabled={props.importing}
      >
        <Plus className="size-3.5" />
        Add EPUB
      </Button>
      {props.files.length > 0 ? (
        <Button
          type="button"
          variant="ghost"
          size="sm"
          onClick={props.onClear}
          disabled={props.importing}
        >
          Clear
        </Button>
      ) : null}
      {props.files.length > 0 ? (
        <span className="ml-auto text-xs text-muted-foreground">
          {props.files.length} · {formatSize(props.total)}
        </span>
      ) : null}
    </div>
  )
}

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}
