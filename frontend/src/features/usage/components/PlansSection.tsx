import { usePlans } from '../hooks/usePlans'
import { PlanCard } from './PlanCard'

/** Manual tier switching (pre-Stripe). Hidden when the runtime flag is off. */
export function PlansSection() {
  const { data } = usePlans()
  if (!data || !data.can_switch) return null
  return (
    <section className="space-y-3">
      <h2 className="text-sm font-semibold">Plans</h2>
      <div className="grid gap-3 sm:grid-cols-2">
        {data.plans.map((plan) => (
          <PlanCard key={plan.slug} plan={plan} />
        ))}
      </div>
    </section>
  )
}
