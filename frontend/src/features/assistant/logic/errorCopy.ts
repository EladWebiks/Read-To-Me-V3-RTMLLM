/** Maps structured chat SSE errors to user-facing copy (spec §6). */
import type { ChatUiLang } from '@/shared/lib/textDirection'
import i18n from '@/shared/i18n'

export function chatErrorMessage(
  detail: string,
  code?: string,
  resetsAt?: string,
  lng: ChatUiLang = 'en',
): string {
  if (code === 'quota_exceeded') {
    return i18n.t('assistant:errors.quota', { lng, date: rolloverLabel(resetsAt, lng) })
  }
  return friendlyProviderCopy(detail, lng)
}

function friendlyProviderCopy(detail: string, lng: ChatUiLang): string {
  const text = detail.toLowerCase()
  if (!text.trim()) {
    return i18n.t('assistant:errors.generic', { lng })
  }
  if (looksBusy(text)) {
    return i18n.t('assistant:errors.busy', { lng })
  }
  if (looksRateLimited(text)) {
    return i18n.t('assistant:errors.rateLimited', { lng })
  }
  if (looksTimeout(text) || looksDeadline(text)) {
    return i18n.t('assistant:errors.timeout', { lng })
  }
  if (looksAuth(text)) {
    return i18n.t('assistant:errors.auth', { lng })
  }
  if (looksProviderDump(text)) {
    return i18n.t('assistant:errors.providerDump', { lng })
  }
  return detail
}

function looksBusy(text: string): boolean {
  return (
    text.includes('high demand') ||
    text.includes('503') ||
    text.includes('unavailable') ||
    text.includes('service unavailable')
  )
}

function looksRateLimited(text: string): boolean {
  return (
    text.includes('429') ||
    text.includes('rate limit') ||
    text.includes('resource_exhausted')
  )
}

function looksTimeout(text: string): boolean {
  return text.includes('timeout') || text.includes('timed out')
}

function looksDeadline(text: string): boolean {
  return text.includes('run deadline') || text.includes('deadline exceeded')
}

function looksAuth(text: string): boolean {
  return (
    text.includes('api key') ||
    text.includes('401') ||
    text.includes('403') ||
    text.includes('permission_denied') ||
    text.includes('unauthenticated')
  )
}

/** Raw SDK / HTTP blobs — never show these to end users. */
function looksProviderDump(text: string): boolean {
  return (
    text.includes("{'message'") ||
    text.includes('"error"') ||
    text.includes('status":') ||
    text.includes('spikes in demand') ||
    (text.includes('{') && text.includes('}'))
  )
}

function rolloverLabel(resetsAt: string | undefined, lng: ChatUiLang): string {
  if (!resetsAt) return i18n.t('assistant:errors.quotaNextMonth', { lng })
  const date = new Date(resetsAt)
  if (Number.isNaN(date.getTime()))
    return i18n.t('assistant:errors.quotaNextMonth', { lng })
  return date.toLocaleDateString(lng === 'he' ? 'he-IL' : undefined, {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
  })
}
