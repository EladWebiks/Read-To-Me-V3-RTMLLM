import type { ConfirmationFormField } from '../api/chatApi'
import { stringValue } from './confirmFormUtils'
import type { TtsProviderName } from '@/features/reader/hooks/ttsSettingsStore'
import { useServerVoices } from '@/features/reader/hooks/useServerVoices'
import { Select } from '@/shared/ui'

type Props = {
  field: ConfirmationFormField
  values: Record<string, unknown>
  busy: boolean
  onChange: (name: string, value: unknown) => void
}

export function ConfirmationVoiceControl(props: Props) {
  const provider: TtsProviderName = props.values.provider === 'sapi' ? 'sapi' : 'edge'
  const voices = useServerVoices(provider)
  return (
    <Select
      size="sm"
      className="w-full"
      disabled={props.busy || voices.isLoading}
      value={stringValue(props.values.voice)}
      onChange={(event) => props.onChange(props.field.name, event.target.value || null)}
    >
      <option value="">Provider default</option>
      {(voices.data ?? []).map((voice) => (
        <option key={voice.id} value={voice.id}>
          {voice.name}
          {voice.locale ? ` (${voice.locale})` : ''}
        </option>
      ))}
    </Select>
  )
}
