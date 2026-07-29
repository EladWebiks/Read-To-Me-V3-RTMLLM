import type { ConfirmationFormField, ConfirmationPayload } from '../api/chatApi'
import {
  defaultDownloadRate,
  defaultVoice,
} from '@/features/downloads/logic/audioModalUtils'
import type { TtsProviderName } from '@/features/reader/hooks/ttsSettingsStore'

export type AudioConfirmationDefaults = {
  provider: TtsProviderName
  serverVoice: string | null
  rate: number
}

export function defaultsFrom(
  payload: ConfirmationPayload,
  audio?: AudioConfirmationDefaults,
): Record<string, unknown> {
  const out: Record<string, unknown> = { ...payload.args }
  for (const field of payload.form?.fields ?? []) {
    const audioDefault = audioFieldDefault(payload.tool, field, out, audio)
    if (audioDefault !== undefined) {
      out[field.name] = audioDefault
    } else if (out[field.name] === undefined) {
      out[field.name] = field.default
    }
  }
  return out
}

function audioFieldDefault(
  tool: string,
  field: ConfirmationFormField,
  values: Record<string, unknown>,
  settings?: AudioConfirmationDefaults,
): unknown {
  if (tool !== 'create_audio_download' || field.provided !== false || !settings) {
    return undefined
  }
  if (field.name === 'provider') return settings.provider
  if (field.name === 'rate') {
    const provider = values.provider === 'sapi' ? 'sapi' : 'edge'
    return defaultDownloadRate(provider, settings.rate)
  }
  if (field.name === 'voice') {
    const provider = values.provider === 'sapi' ? 'sapi' : 'edge'
    return defaultVoice(provider, settings.serverVoice)
  }
  return undefined
}

export function stringValue(value: unknown): string {
  if (value === null || value === undefined) return ''
  return String(value)
}

export function coerce(field: ConfirmationFormField, raw: string): unknown {
  if (raw.trim() === '') return null
  if (field.type === 'integer') {
    const n = Number.parseInt(raw, 10)
    return Number.isFinite(n) ? n : null
  }
  if (field.type === 'number') {
    const n = Number.parseFloat(raw)
    return Number.isFinite(n) ? n : null
  }
  return raw
}

export function formValues(
  fields: ConfirmationFormField[],
  values: Record<string, unknown>,
): Record<string, unknown> {
  const out: Record<string, unknown> = {}
  for (const field of fields) out[field.name] = values[field.name]
  return out
}

export function validateFields(
  fields: ConfirmationFormField[],
  values: Record<string, unknown>,
): string | null {
  for (const field of fields) {
    const value = values[field.name]
    if (value === null || value === undefined || value === '') {
      if (field.required) return `${field.label} is required`
      continue
    }
    if (typeof value === 'number') {
      if (field.min !== undefined && value < field.min) {
        return `${field.label} must be ≥ ${field.min}`
      }
      if (field.max !== undefined && value > field.max) {
        return `${field.label} must be ≤ ${field.max}`
      }
    }
  }
  return null
}
