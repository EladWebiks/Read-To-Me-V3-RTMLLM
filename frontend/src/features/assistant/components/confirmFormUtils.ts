import type { ConfirmationFormField, ConfirmationPayload } from '../api/chatApi'

export function defaultsFrom(payload: ConfirmationPayload): Record<string, unknown> {
  const out: Record<string, unknown> = { ...payload.args }
  for (const field of payload.form?.fields ?? []) {
    if (out[field.name] === undefined) out[field.name] = field.default
  }
  return out
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
