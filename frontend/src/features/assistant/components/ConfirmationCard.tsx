import { useState } from 'react'
import { useTtsSettings } from '@/features/reader/hooks/ttsSettingsStore'
import type { ConfirmationPayload } from '../api/chatApi'
import { ConfirmFields } from './ConfirmationFields'
import { defaultsFrom, formValues, validateFields } from './confirmFormUtils'

type Props = {
  payload: ConfirmationPayload
  busy: boolean
  onResolve: (approved: boolean, values?: Record<string, unknown>) => void
}

/** Form / binary HITL card for confirmation_required tools. */
export function ConfirmationCard({ payload, busy, onResolve }: Props) {
  const tts = useTtsSettings()
  const [values, setValues] = useState(() =>
    defaultsFrom(payload, {
      provider: tts.provider,
      serverVoice: tts.serverVoice,
      rate: tts.rate,
    }),
  )
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
        tool={payload.tool}
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
