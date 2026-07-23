import { useAppSettings } from '@/features/settings/settingsStore'
import type { PlayerControlsProps } from '@/features/reader/logic/playerControlTypes'

export function RateVolumeControls(props: PlayerControlsProps) {
  const maxRate = useAppSettings((s) => s.maxRate)
  return (
    <>
      <label className="flex items-center gap-1 text-sm">
        Speed
        <input
          type="range"
          min={0.5}
          max={maxRate}
          step={0.1}
          value={props.rate}
          onChange={(e) => props.onRate(Number(e.target.value))}
        />
        <span className="w-8 tabular-nums">{props.rate.toFixed(1)}</span>
      </label>
      <label className="flex items-center gap-1 text-sm">
        Volume
        <input
          type="range"
          min={0}
          max={1}
          step={0.05}
          value={props.volume}
          onChange={(e) => props.onVolume(Number(e.target.value))}
        />
      </label>
      <label className="flex items-center gap-1 text-sm">
        <input
          type="checkbox"
          checked={props.autoNext}
          onChange={(e) => props.onAutoNext(e.target.checked)}
        />
        Auto-next
      </label>
    </>
  )
}
