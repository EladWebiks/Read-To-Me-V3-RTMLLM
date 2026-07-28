import { useState } from 'react'
import type { ConfirmationFormField, ConfirmationPayload } from '../api/chatApi'
import {
  coerce,
  defaultsFrom,
  formValues,
  stringValue,
  validateFields,
} from './confirmFormUtils'

type Props = {
  payload: ConfirmationPayload
  busy: boolean
  onResolve: (approved: boolean, values?: Record<string, unknown>) => void
}

/** Form / binary HITL card for confirmation_required tools. */
export function ConfirmationCard({ payload, busy, onResolve }: Props) {
  const [values, setValues] = useState(() => defaultsFrom(payload))
  const [error, setError] = useState<string | null>(null)
  if (payload.status !== 'pending') return <ResolvedConfirm payload={payload} />

  const fields = payload.form?.fields ?? []
  const submit = () => {
    const issue = validateFields(fields, values)
    if (issue) {
      setError(issue)
      return
    }
    setError(null)
    onResolve(true, formValues(fields, values))
  }

  return (
    <div className="rounded-2xl border border-amber-500/40 bg-amber-500/10 px-3.5 py-3 text-sm">
      <p className="font-medium text-foreground">{payload.summary}</p>
      <p className="mt-1 text-xs text-muted-foreground">
        Confirm <span className="font-mono">{payload.tool}</span> before it runs.
      </p>
      <ConfirmFields
        fields={fields}
        values={values}
        busy={busy}
        onChange={(name, value) => {
          setError(null)
          setValues((prev) => ({ ...prev, [name]: value }))
        }}
      />
      {error ? <p className="mt-2 text-xs text-destructive">{error}</p> : null}
      <div className="mt-3 flex gap-2">
        <button
          type="button"
          disabled={busy}
          onClick={submit}
          className="rounded-xl bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground disabled:opacity-50"
        >
          OK
        </button>
        <button
          type="button"
          disabled={busy}
          onClick={() => onResolve(false)}
          className="rounded-xl border border-border bg-background px-3 py-1.5 text-sm disabled:opacity-50"
        >
          Cancel
        </button>
      </div>
    </div>
  )
}

function ResolvedConfirm({ payload }: { payload: ConfirmationPayload }) {
  const label = payload.status === 'approved' ? 'Approved' : 'Declined'
  return (
    <div className="rounded-2xl border border-border bg-muted/40 px-3.5 py-2.5 text-sm text-muted-foreground">
      {label} — {payload.summary}
    </div>
  )
}

type FieldsProps = {
  fields: ConfirmationFormField[]
  values: Record<string, unknown>
  busy: boolean
  onChange: (name: string, value: unknown) => void
}

function ConfirmFields({ fields, values, busy, onChange }: FieldsProps) {
  if (fields.length === 0) return null
  return (
    <div className="mt-3 space-y-2">
      {fields.map((field) => (
        <label key={field.name} className="block space-y-1">
          <span className="text-xs font-medium text-muted-foreground">{field.label}</span>
          <input
            type={field.type === 'integer' || field.type === 'number' ? 'number' : 'text'}
            min={field.min}
            max={field.max}
            step={field.type === 'integer' ? 1 : undefined}
            disabled={busy}
            value={stringValue(values[field.name])}
            onChange={(e) => onChange(field.name, coerce(field, e.target.value))}
            className="w-full rounded-lg border border-border bg-background px-2.5 py-1.5 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-60"
          />
        </label>
      ))}
    </div>
  )
}
