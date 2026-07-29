import type { ConfirmationFormField } from '../api/chatApi'
import { stringValue } from './confirmFormUtils'
import type { TtsProviderName } from '@/features/reader/hooks/ttsSettingsStore'
import { useServerVoices } from '@/features/reader/hooks/useServerVoices'

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
    <select
      disabled={props.busy || voices.isLoading}
      value={stringValue(props.values.voice)}
      onChange={(event) => props.onChange(props.field.name, event.target.value || null)}
      className="w-full rounded-lg border border-border bg-background px-2.5 py-1.5 text-sm"
    >
      <option value="">Provider default</option>
      {(voices.data ?? []).map((voice) => (
        <option key={voice.id} value={voice.id}>
          {voice.name}
          {voice.locale ? ` (${voice.locale})` : ''}
        </option>
      ))}
    </select>
  )
}
