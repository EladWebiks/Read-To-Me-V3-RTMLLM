import { Loader2 } from 'lucide-react'
import type { ConversationSummary } from '../api/chatApi'
import { Button } from '@/shared/ui'
import { HistoryRow } from './HistoryRow'

type Props = {
  loading: boolean
  error: boolean
  items: ConversationSummary[]
  activeId: string | null
  selecting: boolean
  deletingId: string | null
  onSelect: (id: string) => void
  onDelete: (id: string) => void
  onRetry: () => void
}

export function ChatHistoryDrawerBody(props: Props) {
  if (props.loading) return <HistoryLoadingState />
  if (props.error) return <HistoryErrorState onRetry={props.onRetry} />
  if (props.items.length === 0) return <HistoryEmptyState />
  return <HistoryList {...props} />
}

function HistoryLoadingState() {
  return (
    <div className="flex flex-1 items-center justify-center gap-2 text-sm text-muted-foreground">
      <Loader2 className="h-4 w-4 animate-spin" />
      Loading…
    </div>
  )
}

function HistoryErrorState({ onRetry }: { onRetry: () => void }) {
  return (
    <div className="flex flex-1 flex-col items-center justify-center gap-2 px-4 text-center">
      <p className="text-sm text-muted-foreground">Couldn't load history.</p>
      <Button type="button" variant="outline" size="sm" onClick={onRetry}>
        Retry
      </Button>
    </div>
  )
}

function HistoryEmptyState() {
  return (
    <div className="flex flex-1 items-center justify-center px-6 text-center text-sm text-muted-foreground">
      No conversations yet. Send a message to start one.
    </div>
  )
}

function HistoryList({
  items,
  activeId,
  selecting,
  deletingId,
  onSelect,
  onDelete,
}: Props) {
  return (
    <ul className="min-h-0 flex-1 space-y-1 overflow-y-auto p-2">
      {items.map((item, index) => (
        <HistoryRow
          key={item.id}
          item={item}
          active={item.id === activeId}
          disabled={selecting || deletingId !== null}
          deleting={deletingId === item.id}
          index={index}
          onSelect={onSelect}
          onDelete={onDelete}
        />
      ))}
    </ul>
  )
}
