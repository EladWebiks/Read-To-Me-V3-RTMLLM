import { isoToLocal, localToIso, type Period } from '@/features/admin/logic/period'

const INPUT = 'rounded border border-border bg-background px-2 py-1'

export function DateRangeField({
  period,
  onChange,
}: {
  period: Period
  onChange: (period: Period) => void
}) {
  return (
    <div className="flex flex-wrap items-end gap-2 text-sm">
      <label className="flex flex-col gap-1">
        <span className="text-xs text-muted-foreground">From</span>
        <input
          type="datetime-local"
          className={INPUT}
          value={isoToLocal(period.from)}
          onChange={(event) =>
            onChange({ ...period, from: localToIso(event.target.value) })
          }
        />
      </label>
      <label className="flex flex-col gap-1">
        <span className="text-xs text-muted-foreground">To (exclusive)</span>
        <input
          type="datetime-local"
          className={INPUT}
          value={isoToLocal(period.to)}
          onChange={(event) =>
            onChange({ ...period, to: localToIso(event.target.value) })
          }
        />
      </label>
    </div>
  )
}
