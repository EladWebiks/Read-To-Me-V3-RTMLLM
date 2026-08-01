import { InlineLoader, QueryState } from '@/shared/ui'
import { ChapterRow } from './ChapterRow'
import type { ChapterSummary } from '@/features/library/types'

type Props = {
  loading: boolean
  errored: boolean
  chapters: ChapterSummary[]
  lastRead: number | null
  onPlay: (id: string) => void
  onEdit: (id: string) => void
  onDelete: (id: string) => void
  onRetry: () => void
}

export function ChapterRows(props: Props) {
  return (
    <QueryState
      isPending={props.loading}
      isError={props.errored}
      loading={<InlineLoader label="Loading chapters…" />}
      errorLabel="Couldn't load chapters."
      label="Loading chapters…"
      onRetry={props.onRetry}
    >
      <div className="min-h-0 flex-1 overflow-y-auto rounded-md border border-border">
        <table className="w-full text-sm">
          <thead className="sticky top-0 bg-muted/80 text-left">
            <tr>
              <th className="px-3 py-2 font-medium">#</th>
              <th className="px-3 py-2 font-medium">Title</th>
              <th className="px-3 py-2 font-medium">Actions</th>
            </tr>
          </thead>
          <tbody>
            {props.chapters.map((ch) => (
              <ChapterRow
                key={ch.id}
                chapter={ch}
                isLastRead={props.lastRead === ch.chapter_number}
                onPlay={() => props.onPlay(ch.id)}
                onEdit={() => props.onEdit(ch.id)}
                onDelete={() => props.onDelete(ch.id)}
              />
            ))}
          </tbody>
        </table>
      </div>
    </QueryState>
  )
}
