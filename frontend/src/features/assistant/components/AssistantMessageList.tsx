import { MessageSquare } from 'lucide-react'
import type { ChatMessage } from '../api/chatApi'
import { useStickToBottom } from '../hooks/useStickToBottom'
import { ChatTurn } from './ChatTurn'

type Props = {
  messages: ChatMessage[]
  framed: boolean
  error: string | null
  sending: boolean
}

/** Scrollable message list or empty state. */
export function AssistantMessageList({ messages, framed, error, sending }: Props) {
  const last = messages[messages.length - 1]
  const contentKey = `${messages.length}:${last?.id ?? ''}:${last?.content.length ?? 0}`
  const { containerRef, onScroll } = useStickToBottom(sending, contentKey)

  if (!messages.length) {
    return <EmptyState framed={framed} />
  }

  return (
    <div
      ref={containerRef}
      onScroll={onScroll}
      className="assistant-scroll min-h-0 flex-1 space-y-4 overflow-y-auto px-3 py-3 sm:px-4"
    >
      {messages.map((m, index) => (
        <ChatTurn
          key={m.id}
          message={m}
          streaming={sending && m.role === 'assistant' && index === messages.length - 1}
        />
      ))}
      {error ? (
        <div
          role="alert"
          className="rounded-2xl border border-destructive/35 bg-destructive/10 px-3.5 py-2.5 text-sm text-destructive"
        >
          {error}
        </div>
      ) : null}
    </div>
  )
}

function EmptyState({ framed }: { framed: boolean }) {
  return (
    <div
      className={`flex min-h-0 flex-1 flex-col items-center justify-center gap-3 px-6 py-8 text-center ${
        framed ? 'bg-gradient-to-b from-muted/20 to-transparent' : ''
      }`}
    >
      <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-gradient-to-br from-indigo-500/20 via-fuchsia-500/15 to-amber-400/20 text-foreground/80">
        <MessageSquare className="h-6 w-6" />
      </div>
      <div className="max-w-sm space-y-1.5">
        <p className="text-sm font-medium text-foreground">Ask anything</p>
        <p className="text-sm leading-relaxed text-muted-foreground">
          Free-form chat for now. Library tools and actions come next.
        </p>
      </div>
    </div>
  )
}
