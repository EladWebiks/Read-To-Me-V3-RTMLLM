import { useTtsSettings } from '@/features/reader/hooks/ttsSettingsStore'
import {
  defaultDownloadRate,
  defaultVoice,
} from '@/features/downloads/logic/audioModalUtils'
import type { ConfirmationFormField } from '../api/chatApi'
import { ConfirmationFieldControl } from './ConfirmationFieldControl'
import { fieldRows, shortLabel } from './confirmFieldLayout'

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
    <div className="mt-2.5 space-y-2">
      {fieldRows(props.fields).map((row) =>
        row.length === 2 ? (
          <div key={row.map((f) => f.name).join('-')} className="grid grid-cols-2 gap-2">
            {row.map((field) => (
              <FieldLabel
                key={field.name}
                tool={props.tool}
                field={field}
                values={props.values}
                busy={props.busy}
                onChange={change}
                compact
              />
            ))}
          </div>
        ) : (
          <FieldLabel
            key={row[0]!.name}
            tool={props.tool}
            field={row[0]!}
            values={props.values}
            busy={props.busy}
            onChange={change}
          />
        ),
      )}
    </div>
  )
}

function FieldLabel(props: {
  tool: string
  field: ConfirmationFormField
  values: Record<string, unknown>
  busy: boolean
  onChange: (name: string, value: unknown) => void
  compact?: boolean
}) {
  return (
    <label className="block min-w-0 space-y-1">
      <span className="text-xs font-medium text-muted-foreground">
        {props.compact ? shortLabel(props.field) : props.field.label}
      </span>
      <ConfirmationFieldControl {...props} />
    </label>
  )
}
