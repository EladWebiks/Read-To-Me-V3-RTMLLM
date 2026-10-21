import { Send, Square } from 'lucide-react'
import { useTranslation } from 'react-i18next'

export function ComposerSendButton({
  sending,
  sendDisabled,
  onCancel,
}: {
  sending: boolean
  sendDisabled: boolean
  onCancel?: () => void
}) {
  const { t } = useTranslation('assistant', { lng: 'en' })
  if (sending) {
    return (
      <button
        type="button"
        onClick={onCancel}
        className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-destructive/10 text-destructive transition hover:bg-destructive/20"
        aria-label={t('composer.stopAria')}
      >
        <Square className="size-3.5 fill-current" />
      </button>
    )
  }
  return (
    <button
      type="submit"
      disabled={sendDisabled}
      className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-primary text-primary-foreground transition hover:opacity-90 disabled:opacity-40"
      aria-label={t('composer.sendAria')}
    >
      <Send className="size-4" />
    </button>
  )
}
