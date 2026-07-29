import { Button } from '@/shared/ui'
import type { ChoicePayload } from '../api/chatApi'

type Props = {
  payload: ChoicePayload
  disabled?: boolean
  onPick: (label: string) => void
}

/** Clarify chips — picking one sends a normal user message. */
export function ChoiceChips({ payload, disabled = false, onPick }: Props) {
  return (
    <div className="rounded-2xl border border-border bg-muted/30 px-3.5 py-2.5 text-sm">
      <p className="text-foreground">{payload.prompt}</p>
      <div className="mt-2 flex flex-wrap gap-2">
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
