import { MessageSquare } from 'lucide-react'
import { ASSISTANT_CHAT_COLUMN } from './assistantGeometry'

/** Milestone A placeholder chat surface (LLM lands in B). */
export function AssistantChatPlaceholder({ expanded = false }: { expanded?: boolean }) {
  if (!expanded) {
    return <ChatBody framed={false} />
  }

  return (
    <div className="flex min-h-0 flex-1 flex-col bg-muted/25 px-3 py-3 sm:px-4 sm:py-4">
      <div
        className={`${ASSISTANT_CHAT_COLUMN} overflow-hidden rounded-2xl border border-border bg-card shadow-sm ring-1 ring-black/[0.03]`}
      >
        <ChatBody framed />
      </div>
    </div>
  )
}

function ChatBody({ framed }: { framed: boolean }) {
  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div
        className={`flex min-h-0 flex-1 flex-col items-center justify-center gap-3 px-6 py-8 text-center ${
          framed ? 'bg-gradient-to-b from-muted/20 to-transparent' : ''
        }`}
      >
        <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-gradient-to-br from-indigo-500/20 via-fuchsia-500/15 to-amber-400/20 text-foreground/80">
          <MessageSquare className="h-6 w-6" />
        </div>
        <div className="max-w-sm space-y-1.5">
          <p className="text-sm font-medium text-foreground">Ready when tools land</p>
          <p className="text-sm leading-relaxed text-muted-foreground">
            Ask about your library, start reading, or kick off a scrape — the assistant
            will act through audited tools, not raw access.
          </p>
        </div>
      </div>
      <div className="shrink-0 border-t border-border p-3 sm:p-4">
        <div
          aria-disabled="true"
          className="rounded-xl border border-dashed border-border bg-muted/40 px-3 py-2.5 text-sm text-muted-foreground"
        >
          Ask anything about your library…
        </div>
      </div>
    </div>
  )
}
