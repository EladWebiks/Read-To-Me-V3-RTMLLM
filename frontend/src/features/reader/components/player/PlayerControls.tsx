import type { PlaybackEngine } from '@/features/reader/hooks/ttsSettingsStore'
import type { PlayerControlsProps } from '@/features/reader/logic/playerControlTypes'
import { RateVolumeControls } from './RateVolumeControls'
import { VoicePickers } from './VoicePickers'

export type { PlayerControlsProps } from '@/features/reader/logic/playerControlTypes'

export function PlayerControls(props: PlayerControlsProps) {
  return (
    <div className="flex flex-wrap items-center gap-3 text-sm text-stone-600">
      <label className="flex items-center gap-1">
        Engine
        <select
          className="border border-stone-300 bg-white px-2 py-1"
          value={props.engine}
          onChange={(event) => props.onEngine(event.target.value as PlaybackEngine)}
        >
          <option value="browser">Browser</option>
          <option value="server">Server</option>
        </select>
      </label>
      <VoicePickers {...props} />
      <RateVolumeControls {...props} />
    </div>
  )
}
