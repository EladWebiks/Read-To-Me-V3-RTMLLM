import { Button } from '@/shared/ui'
import type { ChoicePayload } from '../api/chatApi'
import { hitlCardClass } from './hitlCardChrome'

type Props = {
  payload: ChoicePayload
  disabled?: boolean
  onPick: (label: string) => void
}

/** Clarify chips — picking one sends a normal user message. */
export function ChoiceChips({ payload, disabled = false, onPick }: Props) {
  return (
    <div className={hitlCardClass}>
      <p className="text-[11px] font-semibold uppercase tracking-wide text-violet-600 dark:text-violet-300">
        Choose
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
