import { Button, Card, CardContent, CardHeader, CardTitle } from '@/shared/ui'
import type { Plan } from '../api/plans'
import { useSwitchPlan } from '../hooks/usePlans'

/** One tier in the plan picker: current-plan badge, or a confirm-gated switch button. */
export function PlanCard({ plan }: { plan: Plan }) {
  const switchTo = useSwitchPlan()

  const onSwitch = () => {
    if (window.confirm(`Switch to ${plan.label}?`)) {
      switchTo.mutate(plan.slug)
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-baseline justify-between gap-2">
          <span>{plan.label}</span>
          {plan.price_label && (
            <span className="text-xs font-normal text-muted-foreground">
              {plan.price_label}
            </span>
          )}
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        {plan.description && (
          <p className="text-sm text-muted-foreground">{plan.description}</p>
        )}
        {plan.current ? (
          <span className="text-xs font-medium text-muted-foreground">Current plan</span>
        ) : (
          <Button
            type="button"
            size="sm"
            onClick={onSwitch}
            disabled={switchTo.isPending}
          >
            Switch to {plan.label}
          </Button>
        )}
      </CardContent>
    </Card>
  )
}
