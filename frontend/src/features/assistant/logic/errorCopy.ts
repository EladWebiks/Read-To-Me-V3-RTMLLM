/** Maps structured chat SSE errors to user-facing copy (spec §6). */

export function chatErrorMessage(
  detail: string,
  code?: string,
  resetsAt?: string,
): string {
  if (code === 'quota_exceeded') {
    return `You've reached your monthly AI limit. Upgrade your plan or try again after ${rolloverLabel(resetsAt)}.`
  }
  return friendlyProviderCopy(detail)
}

function friendlyProviderCopy(detail: string): string {
  const text = detail.toLowerCase()
  if (!text.trim()) {
    return 'Something went wrong. Please try again.'
  }
  if (looksBusy(text)) {
    return 'The AI service is busy right now. Please try again in a moment.'
  }
  if (looksRateLimited(text)) {
    return 'Too many AI requests right now. Please wait a moment and try again.'
  }
  if (looksTimeout(text)) {
    return 'The assistant took too long to respond. Please try again.'
  }
  if (looksAuth(text)) {
    return "The AI service couldn't authenticate. Check your API key settings."
  }
  if (looksProviderDump(text)) {
    return "The assistant couldn't complete that reply. Please try again."
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

function rolloverLabel(resetsAt?: string): string {
  if (!resetsAt) return 'next month'
  const date = new Date(resetsAt)
  if (Number.isNaN(date.getTime())) return 'next month'
  return date.toLocaleDateString(undefined, {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
  })
}
