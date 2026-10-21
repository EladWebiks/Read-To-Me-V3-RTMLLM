import { Link } from 'react-router'
import { useTranslation } from 'react-i18next'
import { Button } from '@/shared/ui'
import type { ChatUiLang } from '@/shared/lib/textDirection'
import { textDirForLang } from '@/shared/lib/textDirection'
import type { ClientAction } from '../api/chatApi'
import { DownloadToolResultCard } from './DownloadToolResultCard'
import { hitlCardClass } from './hitlCardChrome'
import { ScrapeToolResultCard } from './ScrapeToolResultCard'

type Props = {
  name: string
  ok: boolean
  summary: string
  uiLang: ChatUiLang
  clientAction?: ClientAction
}

/** Compact durable tool outcome (e.g. scrape queued). */
export function ToolResultCard({ name, ok, summary, uiLang, clientAction }: Props) {
  if (ok && clientAction?.type === 'download') {
    return (
      <DownloadToolResultCard action={clientAction} summary={summary} uiLang={uiLang} />
    )
  }
  if (ok && clientAction?.type === 'scrape') {
    return (
      <ScrapeToolResultCard
        action={clientAction}
        summary={summary}
        toolName={name}
        uiLang={uiLang}
      />
    )
  }
  if (!ok) return <FailedTool summary={summary} uiLang={uiLang} />
  return (
    <OkTool name={name} summary={summary} uiLang={uiLang} clientAction={clientAction} />
  )
}

function FailedTool({ summary, uiLang }: { summary: string; uiLang: ChatUiLang }) {
  const { t } = useTranslation('assistant', { lng: uiLang })
  return (
    <div
      dir={textDirForLang(uiLang)}
      className="rounded-2xl border border-destructive/40 bg-destructive/10 px-3.5 py-2.5 text-sm"
    >
      <p className="text-[11px] font-semibold uppercase tracking-wide text-destructive">
        {t('tool.failed')}
      </p>
      <p className="mt-1 text-foreground">{summary}</p>
    </div>
  )
}

function OkTool({
  name,
  summary,
  uiLang,
  clientAction,
}: {
  name: string
  summary: string
  uiLang: ChatUiLang
  clientAction?: ClientAction
}) {
  const { t } = useTranslation('assistant', { lng: uiLang })
  const linkAction =
    clientAction &&
    clientAction.type !== 'settings' &&
    clientAction.type !== 'download' &&
    clientAction.type !== 'scrape'
      ? clientAction
      : null
  return (
    <div dir={textDirForLang(uiLang)} className={hitlCardClass}>
      <p className="text-[11px] font-semibold uppercase tracking-wide text-violet-600 dark:text-violet-300">
        {t('tool.done')}
      </p>
      <p className="mt-1 text-foreground">{summary}</p>
      {linkAction ? (
        <div className="mt-2">
          <Button asChild variant="outline" size="sm">
            <Link
              to={linkAction.path}
              state={
                linkAction.type === 'play'
                  ? { autoPlay: true, playbackRequestId: linkAction.path }
                  : undefined
              }
            >
              {linkAction.label}
            </Link>
          </Button>
        </div>
      ) : null}
      <p className="mt-1.5 text-[10px] text-muted-foreground/80">
        {name.replaceAll('_', ' ')}
      </p>
    </div>
  )
}
