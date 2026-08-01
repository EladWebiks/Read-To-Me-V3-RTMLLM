/** Maps structured chat SSE errors to user-facing copy (spec §6). */

export function chatErrorMessage(
  detail: string,
  code?: string,
  resetsAt?: string,
): string {
  if (code === 'quota_exceeded') {
    return `You've reached your monthly AI limit. Upgrade your plan or try again after ${rolloverLabel(resetsAt)}.`
  }
  return detail
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
