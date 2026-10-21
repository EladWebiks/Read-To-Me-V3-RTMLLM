import type { ReactNode } from 'react'
import { Gauge, Volume2 } from 'lucide-react'
import { Slider } from '@/shared/ui'
import { useAppSettings } from '@/features/settings/settingsStore'

type Props = {
  rate: number
  volume: number
  onRate: (rate: number) => void
  onVolume: (volume: number) => void
}

/** Compact centered speed/volume — engine/voice live in Settings. */
export function RateVolumeControls(props: Props) {
  const maxRate = useAppSettings((s) => s.maxRate)
  return (
    <div className="flex flex-wrap items-center justify-center gap-3 sm:gap-4">
      <CompactSlider
        icon={<Gauge className="h-3.5 w-3.5" aria-hidden />}
        label="Speed"
        valueLabel={`${props.rate.toFixed(1)}×`}
        min={0.5}
        max={maxRate}
        step={0.1}
        value={props.rate}
        onChange={props.onRate}
      />
      <CompactSlider
        icon={<Volume2 className="h-3.5 w-3.5" aria-hidden />}
        label="Volume"
        valueLabel={`${Math.round(props.volume * 100)}%`}
        min={0}
        max={1}
        step={0.05}
        value={props.volume}
        onChange={props.onVolume}
      />
    </div>
  )
}

function CompactSlider(props: {
  icon: ReactNode
  label: string
  valueLabel: string
  min: number
  max: number
  step: number
  value: number
  onChange: (value: number) => void
}) {
  return (
    <div
      className="flex items-center gap-2 rounded-full border border-border/80 bg-muted/40 px-3 py-1.5"
      title={props.label}
    >
      <span className="shrink-0 text-muted-foreground">{props.icon}</span>
      <Slider
        className="w-24 sm:w-28"
        min={props.min}
        max={props.max}
        step={props.step}
        value={props.value}
        onValueChange={props.onChange}
        aria-label={props.label}
      />
      <span className="w-10 shrink-0 text-right text-xs tabular-nums text-foreground">
        {props.valueLabel}
      </span>
    </div>
  )
}
