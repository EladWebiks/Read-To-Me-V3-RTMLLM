export type Period = { from: string; to: string }

/** Default range: the last 30 days, as ISO strings. */
export function defaultPeriod(): Period {
  const to = new Date()
  const from = new Date(to.getTime() - 30 * 24 * 60 * 60 * 1000)
  return { from: from.toISOString(), to: to.toISOString() }
}

/** ISO → value for <input type="datetime-local"> (local time, minute precision). */
export function isoToLocal(iso: string): string {
  const date = new Date(iso)
  const pad = (part: number) => String(part).padStart(2, '0')
  const day = `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`
  return `${day}T${pad(date.getHours())}:${pad(date.getMinutes())}`
}

export function localToIso(local: string): string {
  return new Date(local).toISOString()
}
