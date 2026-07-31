import { Send, Square } from 'lucide-react'
import { type FormEvent, type KeyboardEvent } from 'react'
import { cn } from '@/shared/lib/cn'
import { composerPlaceholder } from '../logic/composerPlaceholder'

type Props = {
  draft: string
  setDraft: (value: string) => void
  sending: boolean
  status?: string | null
  blocked?: boolean
  quotaNotice?: string | null
  onSend: () => void
  onCancel?: () => void
}

/** Chat input + send. */
export function AssistantComposer({
  draft,
  setDraft,
  sending,
  status = null,
  blocked = false,
  quotaNotice = null,
  onSend,
  onCancel,
}: Props) {
  const disabled = sending || blocked || Boolean(quotaNotice)
  const submit = (e: FormEvent) => {
    e.preventDefault()
    if (!disabled) onSend()
  }

  const onKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      if (!disabled) onSend()
    }
  }

  return (
    <form onSubmit={submit} className="shrink-0 border-t border-border p-3 sm:p-4">
      {blocked || quotaNotice ? (
        <p className="mb-2 text-xs text-amber-700 dark:text-amber-300">
          {quotaNotice ?? 'Confirm or cancel the pending action above to continue.'}
        </p>
      ) : null}
      <div
        className={cn(
          'assistant-composer flex items-end gap-2 rounded-xl border border-border bg-background p-1.5',
          sending && 'assistant-composer-thinking',
        )}
      >
        <textarea
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={onKeyDown}
          rows={1}
          disabled={disabled}
          placeholder={composerPlaceholder(quotaNotice, blocked, sending, status)}
          className="min-h-9 max-h-28 flex-1 resize-none bg-transparent px-2 py-2 text-sm outline-none disabled:opacity-70"
          aria-label="Message"
        />
        <ComposerButton
          sending={sending}
          sendDisabled={disabled || !draft.trim()}
          onCancel={onCancel}
        />
      </div>
    </form>
  )
}

function ComposerButton(props: {
  sending: boolean
  sendDisabled: boolean
  onCancel?: () => void
}) {
  if (props.sending) {
    return (
      <button
        type="button"
        onClick={props.onCancel}
        className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-destructive/10 text-destructive transition hover:bg-destructive/20"
        aria-label="Stop response"
      >
        <Square className="size-3.5 fill-current" />
      </button>
    )
  }
  return (
    <button
      type="submit"
      disabled={props.sendDisabled}
      className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-primary text-primary-foreground transition hover:opacity-90 disabled:opacity-40"
      aria-label="Send message"
    >
      <Send className="size-4" />
    </button>
  )
}
