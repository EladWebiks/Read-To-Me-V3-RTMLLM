import { type FormEvent, type KeyboardEvent } from 'react'

type Props = {
  draft: string
  setDraft: (value: string) => void
  sending: boolean
  blocked?: boolean
  onSend: () => void
}

/** Chat input + send. */
export function AssistantComposer({
  draft,
  setDraft,
  sending,
  blocked = false,
  onSend,
}: Props) {
  const disabled = sending || blocked
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
      {blocked ? (
        <p className="mb-2 text-xs text-amber-700 dark:text-amber-300">
          Confirm or cancel the pending action above to continue.
        </p>
      ) : null}
      <div className="flex gap-2">
        <textarea
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={onKeyDown}
          rows={1}
          disabled={disabled}
          placeholder={blocked ? 'Waiting for confirmation…' : 'Ask anything…'}
          className="min-h-[40px] max-h-28 flex-1 resize-none rounded-xl border border-border bg-background px-3 py-2 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-60"
          aria-label="Message"
        />
        <button
          type="submit"
          disabled={disabled || !draft.trim()}
          className="shrink-0 rounded-xl bg-primary px-3 py-2 text-sm font-medium text-primary-foreground disabled:opacity-50"
        >
          {sending ? '…' : 'Send'}
        </button>
      </div>
    </form>
  )
}
