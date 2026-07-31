import { useMembershipPolicies } from '@/features/admin/hooks/useMembershipPolicies'
import { PolicyCard } from './PolicyCard'

export function PoliciesPage() {
  const { data, isLoading, error } = useMembershipPolicies()
  if (isLoading) {
    return <p className="text-sm text-muted-foreground">Loading membership policies…</p>
  }
  if (error || !data) {
    return <p className="text-sm text-destructive">Failed to load membership policies.</p>
  }
  return (
    <section>
      <h1 className="mb-1 text-lg font-semibold">Membership AI policies</h1>
      <p className="mb-4 text-sm text-muted-foreground">
        Per-turn caps: blank = inherit the runtime setting. Changes apply on the
        user&apos;s next turn — no restart. (Monthly quotas get their own section here in
        Part B.)
      </p>
      <div className="grid gap-4 lg:grid-cols-2">
        {data.policies.map((policy) => (
          <PolicyCard
            key={policy.membership}
            policy={policy}
            inherited={data.inherited}
          />
        ))}
      </div>
    </section>
  )
}
