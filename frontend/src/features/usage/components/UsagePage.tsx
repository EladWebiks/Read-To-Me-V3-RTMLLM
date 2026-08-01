import type { MeUsage } from '../api/meUsage'
import { QueryState, SkeletonRows } from '@/shared/ui'
import { useMeUsage } from '../hooks/useMeUsage'
import { resetLabel } from '../logic/format'
import { MeterRow } from './MeterRow'
import { PlansSection } from './PlansSection'
import { StorageSection } from './StorageSection'

export function UsagePage() {
  const { data, isPending, isError, refetch } = useMeUsage()
  return (
    <div className="mx-auto max-w-xl space-y-6 p-6">
      <QueryState
        isPending={isPending}
        isError={isError || (!isPending && !data)}
        loading={<SkeletonRows count={3} height="h-12" />}
        errorLabel="Couldn't load usage."
        label="Loading usage…"
        onRetry={() => void refetch()}
      >
        {data ? <UsageContent data={data} /> : null}
      </QueryState>
    </div>
  )
}

function UsageContent({ data }: { data: MeUsage }) {
  const monthly = data.kinds.filter((k) => k.window === 'month')
  const standing = data.kinds.filter((k) => k.window === 'standing')
  return (
    <>
      <header className="space-y-1">
        <h1 className="text-lg font-semibold">Plan &amp; usage</h1>
        <p className="text-sm text-muted-foreground">
          <span>{data.membership_label}</span> plan · Usage resets{' '}
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
    </>
  )
}
