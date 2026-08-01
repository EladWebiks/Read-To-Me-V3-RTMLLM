import { useTtsSettings } from '@/features/reader/hooks/ttsSettingsStore'
import {
  defaultDownloadRate,
  defaultVoice,
} from '@/features/downloads/logic/audioModalUtils'
import type { ConfirmationFormField } from '../api/chatApi'
import { coerce, stringValue } from './confirmFormUtils'
import { ConfirmationVoiceControl } from './ConfirmationVoiceControl'
import { Select } from '@/shared/ui'

type Props = {
  tool: string
  fields: ConfirmationFormField[]
  values: Record<string, unknown>
  busy: boolean
  onChange: (name: string, value: unknown) => void
}

export function ConfirmFields(props: Props) {
  const serverVoice = useTtsSettings((state) => state.serverVoice)
  const savedRate = useTtsSettings((state) => state.rate)
  if (props.fields.length === 0) return null
  const change = (name: string, value: unknown) => {
    if (
      props.tool === 'create_audio_download' &&
      name === 'provider' &&
      (value === 'edge' || value === 'sapi')
    ) {
      props.onChange('voice', defaultVoice(value, serverVoice))
      props.onChange('rate', defaultDownloadRate(value, savedRate))
    }
    props.onChange(name, value)
  }
  return (
    <div className="mt-3 space-y-2">
      {props.fields.map((field) => (
        <label key={field.name} className="block space-y-1">
          <span className="text-xs font-medium text-muted-foreground">{field.label}</span>
          <FieldControl
            tool={props.tool}
            field={field}
            values={props.values}
            busy={props.busy}
            onChange={change}
          />
        </label>
      ))}
    </div>
  )
}

function FieldControl(props: {
  tool: string
  field: ConfirmationFormField
  values: Record<string, unknown>
  busy: boolean
  onChange: (name: string, value: unknown) => void
}) {
  if (props.tool === 'create_audio_download' && props.field.name === 'voice') {
    return <ConfirmationVoiceControl {...props} />
  }
  if (props.field.options?.length) {
    return (
      <Select
        disabled={props.busy}
        value={stringValue(props.values[props.field.name])}
        onChange={(event) => props.onChange(props.field.name, event.target.value)}
      >
        {props.field.options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </Select>
    )
  }
  return (
    <input
      type={
        props.field.type === 'integer' || props.field.type === 'number'
          ? 'number'
          : 'text'
      }
      min={props.field.min}
      max={props.field.max}
      step={props.field.type === 'integer' ? 1 : undefined}
      disabled={props.busy}
      value={stringValue(props.values[props.field.name])}
      onChange={(event) =>
        props.onChange(props.field.name, coerce(props.field, event.target.value))
      }
      className="w-full rounded-lg border border-border bg-background px-2.5 py-1.5 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-60"
    />
  )
}
