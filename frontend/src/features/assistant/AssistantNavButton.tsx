import { AssistantSparklesIcon } from './AssistantSparklesIcon'
import { useAssistantStore } from './assistantStore'
import { useTranslation } from 'react-i18next'
import { IconTooltip } from '@/shared/ui'

/** Navbar AI control — larger, always-animating, clearly clickable. */
export function AssistantNavButton() {
  const open = useAssistantStore((s) => s.open)
  const toggle = useAssistantStore((s) => s.toggle)
  const { t } = useTranslation('assistant')
  const label = open ? t('closeAssistant') : t('openAssistant')
  return (
    <IconTooltip label={label}>
      <button
        type="button"
        aria-label={label}
        aria-expanded={open}
        onClick={toggle}
        className={`assistant-nav-btn inline-flex h-10 w-10 cursor-pointer items-center justify-center rounded-full border border-violet-300/60 bg-gradient-to-br from-indigo-500/15 via-fuchsia-500/15 to-amber-400/15 shadow-sm transition-[transform,box-shadow,background-color] duration-200 hover:scale-110 hover:shadow-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-400 ${
          open ? 'ring-2 ring-violet-400/70' : ''
        }`}
      >
        <AssistantSparklesIcon className="h-6 w-6" />
      </button>
    </IconTooltip>
  )
}
