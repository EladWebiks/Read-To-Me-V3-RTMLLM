import { useMemo, useState } from 'react'
import { Button, TooltipProvider } from '@/shared/ui'
import { useAppSettings } from './settingsStore'
import { AddRegexCutRuleModal } from './AddRegexCutRuleModal'
import { RegexCutRuleRow } from './RegexCutRuleRow'

export function RegexCutRulesSection() {
  const rules = useAppSettings((s) => s.regexCutRules)
  const addRegexCutRule = useAppSettings((s) => s.addRegexCutRule)
  const removeRegexCutRule = useAppSettings((s) => s.removeRegexCutRule)
  const toggleRegexCutRule = useAppSettings((s) => s.toggleRegexCutRule)

  const [open, setOpen] = useState(false)
  const empty = useMemo(() => rules.length === 0, [rules.length])

  return (
    <TooltipProvider>
      <div className="space-y-3 border-t border-border pt-4">
        <div className="space-y-1">
          <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
            Reader text cleanup (regex cuts)
          </p>
          <p className="text-xs text-muted-foreground">
            Add JS RegExp rules that remove matching sections from chapter text.
          </p>
        </div>

        {empty ? (
          <p className="text-sm text-muted-foreground">No regex rules yet.</p>
        ) : (
          <div className="space-y-2">
            {rules.map((rule) => (
              <RegexCutRuleRow
                key={rule.id}
                rule={rule}
                onToggle={toggleRegexCutRule}
                onRemove={removeRegexCutRule}
              />
            ))}
          </div>
        )}

        <div className="flex justify-end">
          <Button type="button" size="sm" variant="default" onClick={() => setOpen(true)}>
            Add rule
          </Button>
        </div>

        <AddRegexCutRuleModal
          open={open}
          onOpenChange={setOpen}
          onAdd={(pattern) => addRegexCutRule(pattern)}
        />
      </div>
    </TooltipProvider>
  )
}
