/** Meter math + unit formatting for usage displays (spec §3.4). */

export type MeterState = 'unlimited' | 'ok' | 'warn' | 'over'

export function meterState(used: number, limit: number | null): MeterState {
  if (limit === null || limit <= 0) return 'unlimited'
  const ratio = used / limit
  if (ratio >= 1) return 'over'
  if (ratio >= 0.8) return 'warn'
  return 'ok'
}

export function meterPercent(used: number, limit: number | null): number {
  if (limit === null || limit <= 0) return 0
  return Math.min(100, Math.max(0, (used / limit) * 100))
}

export function formatAmount(value: number, unit: string): string {
  if (unit === 'bytes') return formatBytes(value)
  if (unit === 'USD') return `$${value.toFixed(2)}`
  return Math.round(value).toLocaleString('en-US')
}

function formatBytes(value: number): string {
  const gb = value / 1024 ** 3
  if (gb >= 1) return `${gb.toFixed(1)} GB`
  return `${(value / 1024 ** 2).toFixed(1)} MB`
}

export function resetLabel(resetsAt: string): string {
  const date = new Date(resetsAt)
  if (Number.isNaN(date.getTime())) return 'next month'
  return date.toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
  })
}
