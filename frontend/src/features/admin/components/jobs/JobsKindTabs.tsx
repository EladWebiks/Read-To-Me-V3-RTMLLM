export type JobsKind = 'scraping' | 'downloads'

const TABS: { id: JobsKind; label: string }[] = [
  { id: 'scraping', label: 'Scraping' },
  { id: 'downloads', label: 'Downloads' },
]

export function JobsKindTabs({
  value,
  onChange,
}: {
  value: JobsKind
  onChange: (kind: JobsKind) => void
}) {
  return (
    <div role="tablist" aria-label="Job kinds" className="flex flex-wrap gap-1">
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
                ? 'rounded-md bg-muted px-2.5 py-1 text-sm font-medium'
                : 'rounded-md px-2.5 py-1 text-sm text-muted-foreground hover:text-foreground'
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
