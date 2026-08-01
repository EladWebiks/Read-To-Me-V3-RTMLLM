import type { PlaybackEngine } from '@/features/reader/hooks/ttsSettingsStore'
import type { PlayerControlsProps } from '@/features/reader/logic/playerControlTypes'
import { Select } from '@/shared/ui'
import { RateVolumeControls } from './RateVolumeControls'
import { VoicePickers } from './VoicePickers'

export type { PlayerControlsProps } from '@/features/reader/logic/playerControlTypes'

export function PlayerControls(props: PlayerControlsProps) {
  return (
    <div className="flex flex-wrap items-center gap-3 text-sm text-muted-foreground">
      <label className="flex items-center gap-1">
        Engine
        <Select
          className="w-auto"
          value={props.engine}
          onChange={(event) => props.onEngine(event.target.value as PlaybackEngine)}
        >
          <option value="browser">Browser</option>
          <option value="server">Server</option>
        </Select>
      </label>
      <VoicePickers {...props} />
      <RateVolumeControls {...props} />
    </div>
  )
}
