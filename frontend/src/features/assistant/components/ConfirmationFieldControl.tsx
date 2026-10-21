import { Select } from '@/shared/ui'
import type { ConfirmationFormField } from '../api/chatApi'
import { coerce, stringValue } from './confirmFormUtils'
import { ConfirmationVoiceControl } from './ConfirmationVoiceControl'

type Props = {
  tool: string
  field: ConfirmationFormField
  values: Record<string, unknown>
  busy: boolean
  onChange: (name: string, value: unknown) => void
}

export function ConfirmationFieldControl(props: Props) {
  if (props.tool === 'create_audio_download' && props.field.name === 'voice') {
    return <ConfirmationVoiceControl {...props} />
  }
  if (props.field.options?.length) {
    return (
      <Select
        size="sm"
        className="w-full focus-visible:ring-inset"
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
      className="h-8 w-full rounded-md border border-border bg-background px-2 py-1 text-sm outline-none focus-visible:border-ring focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring disabled:opacity-60"
    />
  )
}
