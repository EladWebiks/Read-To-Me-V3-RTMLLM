import { Power, PowerOff, Trash2 } from 'lucide-react'
import { Button, IconTooltip, Tooltip, TooltipContent, TooltipTrigger } from '@/shared/ui'
import type { RegexCutRule } from './settingsStore'

type RegexCutRuleRowProps = {
  rule: RegexCutRule
  onToggle: (id: string) => void
  onRemove: (id: string) => void
}

export function RegexCutRuleRow({ rule, onToggle, onRemove }: RegexCutRuleRowProps) {
  const enabled = rule.enabled !== false

  return (
    <div className="flex items-center gap-2 rounded-lg border border-border bg-card px-3 py-2">
      <Tooltip>
        <TooltipTrigger asChild>
          <code
            className={`min-w-0 flex-1 truncate font-mono text-xs ${
              enabled ? 'text-foreground' : 'text-muted-foreground line-through'
            }`}
          >
            {rule.pattern}
          </code>
        </TooltipTrigger>
        <TooltipContent side="top" className="max-w-md break-all font-mono text-[10px]">
          {rule.pattern}
        </TooltipContent>
      </Tooltip>
      <div className="flex shrink-0 items-center gap-0.5">
        <IconTooltip label={enabled ? 'Disable rule' : 'Enable rule'}>
          <Button
            type="button"
            variant="ghost"
            size="sm"
            className={enabled ? 'text-foreground' : 'text-muted-foreground'}
            aria-label={enabled ? 'Disable rule' : 'Enable rule'}
            aria-pressed={enabled}
            onClick={() => onToggle(rule.id)}
          >
            {enabled ? <Power className="h-4 w-4" /> : <PowerOff className="h-4 w-4" />}
          </Button>
        </IconTooltip>
        <IconTooltip label="Remove rule">
          <Button
            type="button"
            variant="ghost"
            size="sm"
            className="text-muted-foreground hover:text-foreground"
            aria-label="Remove rule"
            onClick={() => onRemove(rule.id)}
          >
            <Trash2 className="h-4 w-4" />
          </Button>
        </IconTooltip>
      </div>
    </div>
  )
}
