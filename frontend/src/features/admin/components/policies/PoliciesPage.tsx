import { useMembershipPolicies } from '@/features/admin/hooks/useMembershipPolicies'
import { useMembershipQuotas } from '@/features/admin/hooks/useMembershipQuotas'
import { PolicyCard } from './PolicyCard'
import { QuotaSection } from './QuotaSection'

export function PoliciesPage() {
  const { data, isLoading, error } = useMembershipPolicies()
  const quotas = useMembershipQuotas()
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
        user&apos;s next turn — no restart. Quotas: blank = unlimited.
      </p>
      <div className="grid gap-4 lg:grid-cols-2">
        {data.policies.map((policy) => (
          <PolicyCard key={policy.membership} policy={policy} inherited={data.inherited}>
            {quotas.data ? (
              <QuotaSection
                membership={policy.membership}
                kinds={quotas.data.kinds}
                rows={quotas.data.quotas.filter(
                  (q) => q.membership === policy.membership,
                )}
              />
            ) : null}
          </PolicyCard>
        ))}
      </div>
    </section>
  )
}
