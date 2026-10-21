import type { ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { Button } from '@/shared/ui'
import i18n from '@/shared/i18n'
import type { ChatUiLang } from '@/shared/lib/textDirection'
import { textDirForLang } from '@/shared/lib/textDirection'
import type { ConfirmationPayload } from '../api/chatApi'
import { showConfirmSubtitle } from './confirmFieldLayout'
import { hitlCardClass } from './hitlCardChrome'

type Props = {
  payload: ConfirmationPayload
  uiLang: ChatUiLang
  busy: boolean
  error: string | null
  onApprove: () => void
  onCancel: () => void
  children?: ReactNode
}

/** Pending HITL shell: compact header, scrollable fields, sticky actions. */
export function ConfirmationPending({
  payload,
  uiLang,
  busy,
  error,
  onApprove,
  onCancel,
  children,
}: Props) {
  const { t } = useTranslation('assistant', { lng: uiLang })
  const action = actionLabel(payload, uiLang)
  const headline = payload.title?.trim() || payload.summary
  const fields = payload.form?.fields ?? []
  const subtitle = showConfirmSubtitle(payload.subtitle, fields) ? payload.subtitle : null
  const dir = textDirForLang(uiLang)
  return (
    <div dir={dir} className={`${hitlCardClass} flex max-h-[min(52vh,22rem)] flex-col`}>
      <div className="shrink-0">
        <p
          className={`text-[10px] font-semibold tracking-wide text-violet-600 dark:text-violet-300${
            uiLang === 'en' ? ' uppercase' : ''
          }`}
        >
          {action}
        </p>
        <p className="mt-0.5 text-sm font-semibold leading-snug text-foreground">
          {headline}
        </p>
        {subtitle ? (
          <p className="mt-0.5 text-xs text-muted-foreground">{subtitle}</p>
        ) : null}
      </div>
      <div className="assistant-scroll mt-2 min-h-0 flex-1 overflow-y-auto px-0.5 py-1">
        {children}
      </div>
      {error ? <p className="mt-1.5 shrink-0 text-xs text-destructive">{error}</p> : null}
      <div className="mt-2 flex shrink-0 gap-2 border-t border-border/70 pt-2">
        <Button type="button" size="sm" disabled={busy} onClick={onApprove}>
          {t('hitl.approve')}
        </Button>
        <Button
          type="button"
          size="sm"
          variant="outline"
          disabled={busy}
          onClick={onCancel}
        >
          {t('hitl.cancel')}
        </Button>
      </div>
    </div>
  )
}

export function ResolvedConfirm({
  payload,
  uiLang,
}: {
  payload: ConfirmationPayload
  uiLang: ChatUiLang
}) {
  const { t } = useTranslation('assistant', { lng: uiLang })
  const label = payload.status === 'approved' ? t('hitl.approved') : t('hitl.declined')
  const detail = payload.title?.trim() || payload.summary
  return (
    <div
      dir={textDirForLang(uiLang)}
      className="rounded-2xl border border-border bg-muted/40 px-3.5 py-2.5 text-sm text-muted-foreground"
    >
      <span className="font-medium text-foreground/80">{label}</span>
      {detail ? <span> — {detail}</span> : null}
    </div>
  )
}

const KNOWN_ACTIONS = [
  'import_discovered_book',
  'scrape_book_range',
  'create_audio_download',
] as const

function actionLabel(payload: ConfirmationPayload, lng: ChatUiLang): string {
  const tool = payload.tool
  if ((KNOWN_ACTIONS as readonly string[]).includes(tool)) {
    return i18n.t(`assistant:actions.${tool as (typeof KNOWN_ACTIONS)[number]}`, { lng })
  }
  return payload.action ?? tool.replaceAll('_', ' ')
}
