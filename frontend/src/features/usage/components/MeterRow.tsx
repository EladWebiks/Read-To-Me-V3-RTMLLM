import type { MeUsageKind } from '../api/meUsage'
import { formatAmount, meterPercent, meterState } from '../logic/format'

const BAR_COLOR: Record<string, string> = {
  ok: 'bg-primary',
  warn: 'bg-amber-500',
  over: 'bg-destructive',
}

/** One month-kind meter: label, used/limit, threshold-colored bar. */
export function MeterRow({ kind }: { kind: MeUsageKind }) {
  const state = meterState(kind.used, kind.limit)
  return (
    <div className="space-y-1.5">
      <div className="flex items-baseline justify-between text-sm">
        <span className="font-medium">{kind.label}</span>
        <span className="text-muted-foreground">
          {state === 'unlimited'
            ? `${formatAmount(kind.used, kind.unit)} · Unlimited`
            : `${formatAmount(kind.used, kind.unit)} / ${formatAmount(kind.limit ?? 0, kind.unit)}`}
        </span>
      </div>
      {state !== 'unlimited' && (
        <div
          role="progressbar"
          aria-label={kind.label}
          aria-valuenow={Math.round(meterPercent(kind.used, kind.limit))}
          aria-valuemin={0}
          aria-valuemax={100}
          data-state={state}
          className="h-1.5 overflow-hidden rounded-full bg-muted"
        >
          <div
            className={`h-full rounded-full transition-all ${BAR_COLOR[state]}`}
            style={{ width: `${meterPercent(kind.used, kind.limit)}%` }}
          />
        </div>
      )}
    </div>
  )
}
