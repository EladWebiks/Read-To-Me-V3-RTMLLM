import { useMeUsage } from '../hooks/useMeUsage'
import { resetLabel } from '../logic/format'
import { MeterRow } from './MeterRow'
import { PlansSection } from './PlansSection'
import { StorageSection } from './StorageSection'

export function UsagePage() {
  const { data, isPending, isError } = useMeUsage()
  if (isPending)
    return <p className="p-6 text-sm text-muted-foreground">Loading usage…</p>
  if (isError || !data)
    return <p className="p-6 text-sm text-destructive">Could not load usage.</p>
  const monthly = data.kinds.filter((k) => k.window === 'month')
  const standing = data.kinds.filter((k) => k.window === 'standing')
  return (
    <div className="mx-auto max-w-xl space-y-6 p-6">
      <header className="space-y-1">
        <h1 className="text-lg font-semibold">Plan &amp; usage</h1>
        <p className="text-sm text-muted-foreground">
          <span className="capitalize">{data.membership}</span> plan · Usage resets{' '}
          {resetLabel(data.resets_at)}
        </p>
        {data.exempt && (
          <p className="text-xs text-muted-foreground">No limits apply (admin).</p>
        )}
      </header>
      <section className="space-y-3">
        <h2 className="text-sm font-semibold">This month</h2>
        {monthly.map((kind) => (
          <MeterRow key={kind.kind} kind={kind} />
        ))}
      </section>
      <StorageSection kinds={standing} />
      <PlansSection />
    </div>
  )
}
