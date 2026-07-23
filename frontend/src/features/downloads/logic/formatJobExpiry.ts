/** Human-readable remaining TTL for a job expiry timestamp. */
export function formatJobExpiry(expiresAt: string | null): string {
  if (!expiresAt) return ''
  const ms = new Date(expiresAt).getTime() - Date.now()
  if (Number.isNaN(ms) || ms <= 0) return 'expired'
  const hours = Math.ceil(ms / 3_600_000)
  if (hours < 48) return `expires in ${hours}h`
  return `expires in ${Math.ceil(hours / 24)}d`
}
