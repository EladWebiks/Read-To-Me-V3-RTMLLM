import type { MeUsageKind } from '../api/meUsage'
import { MeterRow } from './MeterRow'

/** Standing (level) meters — no monthly reset; freed assets stop counting. */
export function StorageSection({ kinds }: { kinds: MeUsageKind[] }) {
  if (kinds.length === 0) return null
  return (
    <section className="space-y-3">
      <h2 className="text-sm font-semibold">Storage</h2>
      {kinds.map((kind) => (
        <MeterRow key={kind.kind} kind={kind} />
      ))}
      <p className="text-xs text-muted-foreground">
        Frees up when downloads expire or are deleted.
      </p>
    </section>
  )
}
