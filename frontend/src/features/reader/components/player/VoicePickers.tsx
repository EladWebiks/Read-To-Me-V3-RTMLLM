import type { PlayerControlsProps } from '@/features/reader/logic/playerControlTypes'
import type { TtsProviderName } from '@/features/reader/hooks/ttsSettingsStore'
import { Select } from '@/shared/ui'

export function VoicePickers(props: PlayerControlsProps) {
  if (props.engine === 'server') {
    return (
      <>
        <label className="flex items-center gap-1">
          Provider
          <Select
            className="w-auto"
            value={props.provider}
            onChange={(event) => props.onProvider(event.target.value as TtsProviderName)}
          >
            <option value="edge">Edge</option>
            <option value="sapi">SAPI (Zira)</option>
          </Select>
        </label>
        <label className="flex items-center gap-1">
          Voice
          <Select
            className="w-auto max-w-48"
            value={props.serverVoice ?? ''}
            onChange={(event) => props.onServerVoice(event.target.value || null)}
          >
            <option value="">Default</option>
            {props.serverVoices.map((voice) => (
              <option key={voice.id} value={voice.id}>
                {voice.name}
              </option>
            ))}
          </Select>
        </label>
      </>
    )
  }
  return (
    <label className="flex items-center gap-1">
      Voice
      <Select
        className="w-auto max-w-48"
        value={props.voiceURI ?? ''}
        onChange={(event) => props.onVoice(event.target.value || null)}
      >
        <option value="">Default</option>
        {props.browserVoices.map((voice) => (
          <option key={voice.voiceURI} value={voice.voiceURI}>
            {voice.name}
          </option>
        ))}
      </Select>
    </label>
  )
}
