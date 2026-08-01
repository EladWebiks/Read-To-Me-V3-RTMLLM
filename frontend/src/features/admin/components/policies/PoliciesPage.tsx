import { useState } from 'react'
import { useMemberships } from '@/features/admin/hooks/useMemberships'
import { useMembershipPolicies } from '@/features/admin/hooks/useMembershipPolicies'
import { useMembershipQuotas } from '@/features/admin/hooks/useMembershipQuotas'
import type { MembershipPolicy } from '@/features/admin/api/membershipPolicies'
import { PolicyCard } from './PolicyCard'
import { QuotaSection } from './QuotaSection'
import { TierActions } from './TierActions'
import { TierFormDialog } from './TierFormDialog'

/** A tier with no policy row yet renders all-blank (every field inherits). */
function blankPolicy(slug: string): MembershipPolicy {
  return {
    membership: slug,
    updated_at: '',
    max_tool_iters: null,
    max_external_calls: null,
    max_turn_tokens_in: null,
    max_turn_tokens_out: null,
    max_turn_cost_usd: null,
    run_deadline_seconds: null,
    max_hitl_rounds: null,
  }
}

export function PoliciesPage() {
  const tiers = useMemberships()
  const { data, isLoading, error } = useMembershipPolicies()
  const quotas = useMembershipQuotas()
  const [creating, setCreating] = useState(false)
  if (isLoading || tiers.isLoading) {
    return <p className="text-sm text-muted-foreground">Loading membership policies…</p>
  }
  if (error || !data || tiers.error || !tiers.data) {
    return <p className="text-sm text-destructive">Failed to load membership policies.</p>
  }
  const allTiers = tiers.data.memberships
  return (
    <section>
      <div className="mb-1 flex items-center justify-between">
        <h1 className="text-lg font-semibold">Membership tiers</h1>
        <button
          type="button"
          className="rounded-md bg-primary px-3 py-1.5 text-sm text-primary-foreground"
          onClick={() => setCreating(true)}
        >
          New tier
        </button>
      </div>
      <p className="mb-4 text-sm text-muted-foreground">
        Per-turn caps: blank = inherit the runtime setting. Quotas: blank = unlimited, 0 =
        blocked. Changes apply on the user&apos;s next turn — no restart.
      </p>
      <div className="grid gap-4 lg:grid-cols-2">
        {allTiers.map((tier) => {
          const policy =
            data.policies.find((p) => p.membership === tier.slug) ??
            blankPolicy(tier.slug)
          return (
            <div key={tier.slug} className={tier.is_active ? '' : 'opacity-60'}>
              <PolicyCard
                policy={policy}
                inherited={data.inherited}
                header={<TierActions tier={tier} allTiers={allTiers} />}
              >
                {quotas.data ? (
                  <QuotaSection
                    membership={tier.slug}
                    kinds={quotas.data.kinds}
                    rows={quotas.data.quotas.filter((q) => q.membership === tier.slug)}
                  />
                ) : null}
              </PolicyCard>
            </div>
          )
        })}
      </div>
      <TierFormDialog mode="create" open={creating} onClose={() => setCreating(false)} />
    </section>
  )
}
