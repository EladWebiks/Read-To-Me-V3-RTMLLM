import { Button, Label } from '@/shared/ui'

export function ThemeButtons({
  theme,
  setTheme,
}: {
  theme: string | undefined
  setTheme: (value: string) => void
}) {
  return (
    <div className="flex gap-2">
      {(['light', 'dark', 'system'] as const).map((value) => (
        <Button
          key={value}
          type="button"
          size="sm"
          variant={theme === value ? 'default' : 'outline'}
          onClick={() => setTheme(value)}
        >
          {value}
        </Button>
      ))}
    </div>
  )
}

export function RangeRow(props: {
  id: string
  label: string
  min: number
  max: number
  step: number
  value: number
  onChange: (value: number) => void
}) {
  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between gap-2">
        <Label htmlFor={props.id}>{props.label}</Label>
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

function roundStep(value: number, step: number): number {
  const decimals = String(step).split('.')[1]?.length ?? 0
  return Number(value.toFixed(decimals))
}
