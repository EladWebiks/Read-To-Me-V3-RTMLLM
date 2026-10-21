import { type FormEvent, type KeyboardEvent, type RefObject } from 'react'
import { cn } from '@/shared/lib/cn'
import { chatUiLang, textDirForLang } from '@/shared/lib/textDirection'
import { composerPlaceholder } from '../logic/composerPlaceholder'
import { ComposerSendButton } from './ComposerSendButton'

type Props = {
  draft: string
  setDraft: (value: string) => void
  sending: boolean
  status: string | null
  blocked: boolean
  quotaNotice: string | null
  disabled: boolean
  inputRef: RefObject<HTMLTextAreaElement | null>
  notice: string
  ariaLabel: string
  onSend: () => void
  onCancel?: () => void
}

/** Composer form body (input + send/stop). */
export function ComposerFormFields(props: Props) {
  const { draft, setDraft, sending, disabled, inputRef, onSend, onCancel } = props
  const textDir = textDirForLang(chatUiLang(draft))
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
    <form
      dir="ltr"
      onSubmit={submit}
      className="shrink-0 border-t border-border p-3 sm:p-4"
    >
      <ComposerNotice
        blocked={props.blocked}
        quotaNotice={props.quotaNotice}
        notice={props.notice}
      />
      <div
        className={cn(
          'assistant-composer flex items-end gap-2 rounded-xl border border-border bg-background p-1.5',
          sending && 'assistant-composer-thinking',
        )}
      >
        <textarea
          ref={inputRef}
          dir={textDir}
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={onKeyDown}
          rows={1}
          disabled={disabled}
          placeholder={composerPlaceholder(
            props.quotaNotice,
            props.blocked,
            sending,
            props.status,
            'en',
          )}
          className="min-h-9 max-h-28 flex-1 resize-none bg-transparent px-2 py-2 text-sm outline-none disabled:opacity-70"
          aria-label={props.ariaLabel}
        />
        <ComposerSendButton
          sending={sending}
          sendDisabled={disabled || !draft.trim()}
          onCancel={onCancel}
        />
      </div>
    </form>
  )
}

function ComposerNotice({
  blocked,
  quotaNotice,
  notice,
}: {
  blocked: boolean
  quotaNotice: string | null
  notice: string
}) {
  if (!blocked && !quotaNotice) return null
  return <p className="mb-2 text-xs text-amber-700 dark:text-amber-300">{notice}</p>
}
