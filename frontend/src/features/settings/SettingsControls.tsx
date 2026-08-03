import { CircleHelp } from 'lucide-react'
import { Button, IconTooltip, Label } from '@/shared/ui'

export function SettingLabel(props: { htmlFor?: string; label: string; tip: string }) {
  return (
    <div className="flex items-center gap-1.5">
      <Label htmlFor={props.htmlFor}>{props.label}</Label>
      <IconTooltip label={props.tip}>
        <button
          type="button"
          className="inline-flex text-muted-foreground hover:text-foreground"
          aria-label={`About ${props.label}`}
        >
          <CircleHelp className="h-3.5 w-3.5" />
        </button>
      </IconTooltip>
    </div>
  )
}

export function RangeRow(props: {
  id: string
  label: string
  tip?: string
  min: number
  max: number
  step: number
  value: number
  onChange: (value: number) => void
}) {
  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between gap-2">
        {props.tip ? (
          <SettingLabel htmlFor={props.id} label={props.label} tip={props.tip} />
        ) : (
          <Label htmlFor={props.id}>{props.label}</Label>
        )}
        <RangeStepButtons {...props} />
      </div>
      <input
        id={props.id}
        type="range"
        min={props.min}
        max={props.max}
        step={props.step}
        value={props.value}
        className="w-full accent-primary"
        onChange={(e) => props.onChange(Number(e.target.value))}
      />
    </div>
  )
}

function RangeStepButtons(props: {
  min: number
  max: number
  step: number
  value: number
  onChange: (value: number) => void
}) {
  return (
    <div className="flex gap-1">
      <Button
        type="button"
        size="sm"
        variant="outline"
        aria-label="Decrease"
        disabled={props.value <= props.min}
        onClick={() =>
          props.onChange(
            Math.max(props.min, roundStep(props.value - props.step, props.step)),
          )
        }
      >
        −
      </Button>
      <Button
        type="button"
        size="sm"
        variant="outline"
        aria-label="Increase"
        disabled={props.value >= props.max}
        onClick={() =>
          props.onChange(
            Math.min(props.max, roundStep(props.value + props.step, props.step)),
          )
        }
      >
        +
      </Button>
    </div>
  )
}

function roundStep(value: number, step: number): number {
  const decimals = String(step).split('.')[1]?.length ?? 0
  return Number(value.toFixed(decimals))
}
