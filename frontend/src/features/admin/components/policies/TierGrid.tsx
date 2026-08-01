import type { AdminMembership } from '@/features/admin/api/memberships'
import type {
  MembershipPoliciesResponse,
  MembershipPolicy,
} from '@/features/admin/api/membershipPolicies'
import type { MembershipQuotasResponse } from '@/features/admin/api/membershipQuotas'
import { PolicyCard } from './PolicyCard'
import { QuotaSection } from './QuotaSection'
import { TierActions } from './TierActions'

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

export function TierGrid({
  allTiers,
  data,
  quotas,
}: {
  allTiers: AdminMembership[]
  data: MembershipPoliciesResponse
  quotas: MembershipQuotasResponse | null
}) {
  return (
    <div className="grid gap-4 lg:grid-cols-2">
      {allTiers.map((tier) => {
        const policy =
          data.policies.find((p) => p.membership === tier.slug) ?? blankPolicy(tier.slug)
        return (
          <div key={tier.slug} className={tier.is_active ? '' : 'opacity-60'}>
            <PolicyCard
              policy={policy}
              inherited={data.inherited}
              header={<TierActions tier={tier} allTiers={allTiers} />}
            >
              {quotas ? (
                <QuotaSection
                  membership={tier.slug}
                  kinds={quotas.kinds}
                  rows={quotas.quotas.filter((q) => q.membership === tier.slug)}
                />
              ) : null}
            </PolicyCard>
          </div>
        )
      })}
    </div>
  )
}
