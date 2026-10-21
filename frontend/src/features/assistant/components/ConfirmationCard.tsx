import { useState } from 'react'
import { useTtsSettings } from '@/features/reader/hooks/ttsSettingsStore'
import type { ChatUiLang } from '@/shared/lib/textDirection'
import type { ConfirmationPayload } from '../api/chatApi'
import { ConfirmFields } from './ConfirmationFields'
import { ConfirmationPending, ResolvedConfirm } from './ConfirmationPending'
import { defaultsFrom, formValues, validateFields } from './confirmFormUtils'

type Props = {
  payload: ConfirmationPayload
  uiLang: ChatUiLang
  busy: boolean
  onResolve: (approved: boolean, values?: Record<string, unknown>) => void
}

/** Form / binary HITL card for confirmation_required tools. */
export function ConfirmationCard({ payload, uiLang, busy, onResolve }: Props) {
  const tts = useTtsSettings()
  const [values, setValues] = useState(() =>
    defaultsFrom(payload, {
      provider: tts.provider,
      serverVoice: tts.serverVoice,
      rate: tts.rate,
    }),
  )
  const [error, setError] = useState<string | null>(null)
  if (payload.status !== 'pending') {
    return <ResolvedConfirm payload={payload} uiLang={uiLang} />
  }

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
    <ConfirmationPending
      payload={payload}
      uiLang={uiLang}
      busy={busy}
      error={error}
      onApprove={submit}
      onCancel={() => onResolve(false)}
    >
      <ConfirmFields
        tool={payload.tool}
        fields={fields}
        values={values}
        uiLang={uiLang}
        busy={busy}
        onChange={(name, value) => {
          setError(null)
          setValues((prev) => ({ ...prev, [name]: value }))
        }}
      />
    </ConfirmationPending>
  )
}
