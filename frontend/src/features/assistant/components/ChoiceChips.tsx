import { useTranslation } from 'react-i18next'
import { Button } from '@/shared/ui'
import type { ChatUiLang } from '@/shared/lib/textDirection'
import { textDirForLang } from '@/shared/lib/textDirection'
import type { ChoicePayload } from '../api/chatApi'
import { hitlCardClass } from './hitlCardChrome'

type Props = {
  payload: ChoicePayload
  uiLang: ChatUiLang
  disabled?: boolean
  onPick: (label: string) => void
}

/** Clarify chips — picking one sends a normal user message. */
export function ChoiceChips({ payload, uiLang, disabled = false, onPick }: Props) {
  const { t } = useTranslation('assistant', { lng: uiLang })
  return (
    <div dir={textDirForLang(uiLang)} className={hitlCardClass}>
      <p className="text-[11px] font-semibold uppercase tracking-wide text-violet-600 dark:text-violet-300">
        {t('hitl.choose')}
      </p>
      <p className="mt-1 text-sm font-medium text-foreground">{payload.prompt}</p>
      <div className="mt-2.5 flex flex-wrap gap-2">
        {payload.options.map((opt) => (
          <Button
            key={opt.id}
            type="button"
            variant="outline"
            size="sm"
            disabled={disabled}
            onClick={() => onPick(opt.label)}
          >
            {opt.label}
          </Button>
        ))}
      </div>
    </div>
  )
}
