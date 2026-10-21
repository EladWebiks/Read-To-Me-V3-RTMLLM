import { useRef } from 'react'
import { useTranslation } from 'react-i18next'
import { useComposerAutofocus } from '../hooks/useComposerAutofocus'
import { ComposerFormFields } from './ComposerFormFields'

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

/** Chat input + send. Chrome stays English/LTR; only typed text can go RTL. */
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
  const { t } = useTranslation('assistant', { lng: 'en' })
  const inputRef = useRef<HTMLTextAreaElement>(null)
  const locked = blocked || Boolean(quotaNotice)
  const disabled = sending || locked
  useComposerAutofocus(inputRef, sending, locked)
  return (
    <ComposerFormFields
      draft={draft}
      setDraft={setDraft}
      sending={sending}
      status={status}
      blocked={blocked}
      quotaNotice={quotaNotice}
      disabled={disabled}
      inputRef={inputRef}
      notice={quotaNotice ?? t('composer.blockedNotice')}
      ariaLabel={t('composer.messageAria')}
      onSend={onSend}
      onCancel={onCancel}
    />
  )
}
