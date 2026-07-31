/** Composer placeholder copy, most-blocking reason first. */
export function composerPlaceholder(
  quotaNotice: string | null,
  blocked: boolean,
  sending: boolean,
  status: string | null,
): string {
  if (quotaNotice) return quotaNotice
  if (blocked) return 'Waiting for confirmation…'
  if (sending) return status || 'Assistant is working…'
  return 'Ask anything…'
}
