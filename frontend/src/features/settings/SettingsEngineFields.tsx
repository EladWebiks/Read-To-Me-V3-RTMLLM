import type { ReactNode } from 'react'
import type {
  PlaybackEngine,
  TtsProviderName,
} from '@/features/reader/hooks/ttsSettingsStore'
import { Select } from '@/shared/ui'
import { SettingLabel } from './SettingsControls'

export function EngineFields(props: {
  engine: PlaybackEngine
  provider: TtsProviderName
  onEngine: (value: PlaybackEngine) => void
  onProvider: (value: TtsProviderName) => void
}) {
  return (
    <>
      <LabeledField
        id="tts-engine"
        label="Speech engine"
        tip="Browser uses built-in voices. Server uses Edge or Windows SAPI voices."
      >
        <Select
          id="tts-engine"
          className="w-full"
          value={props.engine}
          onChange={(e) => props.onEngine(e.target.value as PlaybackEngine)}
        >
          <option value="browser">Browser</option>
          <option value="server">Server</option>
        </Select>
      </LabeledField>
      {props.engine === 'server' ? (
        <LabeledField
          id="tts-provider"
          label="TTS provider"
          tip="Edge is cloud voices. SAPI uses Windows voices such as Zira."
        >
          <Select
            id="tts-provider"
            className="w-full"
            value={props.provider}
            onChange={(e) => props.onProvider(e.target.value as TtsProviderName)}
          >
            <option value="edge">Edge</option>
            <option value="sapi">SAPI (Zira)</option>
          </Select>
        </LabeledField>
      ) : null}
    </>
  )
}

export function AutoAdvanceField(props: {
  checked: boolean
  onChange: (value: boolean) => void
}) {
  return (
    <label className="flex items-start gap-2">
      <input
        id="auto-advance"
        type="checkbox"
        className="mt-1"
        checked={props.checked}
        onChange={(e) => props.onChange(e.target.checked)}
      />
      <SettingLabel
        htmlFor="auto-advance"
        label="Auto-advance to next chapter"
        tip="When playback finishes this chapter, automatically open and play the next one."
      />
    </label>
  )
}

function LabeledField(props: {
  id: string
  label: string
  tip: string
  children: ReactNode
}) {
  return (
    <div className="space-y-1.5">
      <SettingLabel htmlFor={props.id} label={props.label} tip={props.tip} />
      {props.children}
    </div>
  )
}
