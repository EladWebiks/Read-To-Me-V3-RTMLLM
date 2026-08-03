export type UsageTab = 'stats' | 'executions'

const TABS: { id: UsageTab; label: string }[] = [
  { id: 'stats', label: 'Statistics' },
  { id: 'executions', label: 'Recent executions' },
]

/** Under-the-dates switcher for AI usage views. */
export function UsageTabs({
  value,
  onChange,
}: {
  value: UsageTab
  onChange: (tab: UsageTab) => void
}) {
  return (
    <div
      role="tablist"
      aria-label="Usage views"
      className="flex flex-wrap gap-1 border-b border-border pb-px"
    >
      {TABS.map((tab) => {
        const selected = value === tab.id
        return (
          <button
            key={tab.id}
            type="button"
            role="tab"
            aria-selected={selected}
            className={
              selected
                ? '-mb-px border-b-2 border-foreground px-3 py-1.5 text-sm font-medium text-foreground'
                : 'px-3 py-1.5 text-sm text-muted-foreground hover:text-foreground'
            }
            onClick={() => onChange(tab.id)}
          >
            {tab.label}
          </button>
        )
      })}
    </div>
  )
}
