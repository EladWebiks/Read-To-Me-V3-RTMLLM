import { Link } from 'react-router'
import { useTranslation } from 'react-i18next'
import { Button } from '@/shared/ui'
import { useScrapeJob } from '@/features/scraping/hooks'
import type { ChatUiLang } from '@/shared/lib/textDirection'
import { textDirForLang } from '@/shared/lib/textDirection'
import type { ScrapeClientAction } from '../api/chatTypes'
import { hitlCardClass } from './hitlCardChrome'
import { ScrapeProgress } from './scrapeCardParts'

type Props = {
  action: ScrapeClientAction
  summary: string
  toolName: string
  uiLang: ChatUiLang
}

/** Live scrape progress in chat — same idea as the audio download card. */
export function ScrapeToolResultCard({ action, summary, toolName, uiLang }: Props) {
  const { t } = useTranslation('assistant', { lng: uiLang })
  const job = useScrapeJob(action.jobId).data
  const done = job?.chapters_done ?? 0
  const total = job?.max_chapters ?? action.maxChapters
  const status = job?.status ?? 'pending'
  return (
    <div dir={textDirForLang(uiLang)} className={hitlCardClass}>
      <p className="text-[11px] font-semibold uppercase tracking-wide text-violet-600 dark:text-violet-300">
        {t('tool.scrape')}
      </p>
      <p className="mt-1 text-foreground">{summary}</p>
      <ScrapeProgress status={status} done={done} total={total} message={job?.message} />
      <div className="mt-2">
        <Button asChild variant="outline" size="sm">
          <Link to="/scraper">{action.label}</Link>
        </Button>
      </div>
      <p className="mt-1.5 text-[10px] text-muted-foreground/80">
        {toolName.replaceAll('_', ' ')}
      </p>
    </div>
  )
}
