import type { PlaybackEngine } from '@/features/reader/hooks/ttsSettingsStore'
import { Select } from '@/shared/ui'
import { SettingLabel } from './SettingsControls'

type Props = {
  engine: PlaybackEngine
  voiceURI: string | null
  serverVoice: string | null
  browserVoices: SpeechSynthesisVoice[]
  serverVoices: Array<{ id: string; name: string }>
  loading: boolean
  onBrowserVoice: (value: string | null) => void
  onServerVoice: (value: string | null) => void
}

export function SettingsVoiceField(props: Props) {
  const server = props.engine === 'server'
  return (
    <div className="space-y-1.5">
      <SettingLabel
        htmlFor="tts-voice"
        label="Voice"
        tip="Which voice reads the chapter aloud. Leave Default to use the engine’s preferred voice."
      />
      <Select
        id="tts-voice"
        className="w-full"
        disabled={server && props.loading}
        value={server ? (props.serverVoice ?? '') : (props.voiceURI ?? '')}
        onChange={(e) => {
          const value = e.target.value || null
          if (server) props.onServerVoice(value)
          else props.onBrowserVoice(value)
        }}
      >
        <option value="">Default</option>
        {server
          ? props.serverVoices.map((voice) => (
              <option key={voice.id} value={voice.id}>
                {voice.name}
              </option>
            ))
          : props.browserVoices.map((voice) => (
              <option key={voice.voiceURI} value={voice.voiceURI}>
                {voice.name}
              </option>
            ))}
      </Select>
    </div>
  )
}
