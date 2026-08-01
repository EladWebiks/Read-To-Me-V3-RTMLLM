import { useState } from 'react'
import { useMemberships } from '@/features/admin/hooks/useMemberships'
import { useMembershipPolicies } from '@/features/admin/hooks/useMembershipPolicies'
import { useMembershipQuotas } from '@/features/admin/hooks/useMembershipQuotas'
import { QueryState, SkeletonRows } from '@/shared/ui'
import { TierFormDialog } from './TierFormDialog'
import { TierGrid } from './TierGrid'

export function PoliciesPage() {
  const tiers = useMemberships()
  const policies = useMembershipPolicies()
  const quotas = useMembershipQuotas()
  const [creating, setCreating] = useState(false)
  const isPending = policies.isLoading || tiers.isLoading
  const isError =
    Boolean(policies.error || tiers.error) ||
    (!isPending && (!policies.data || !tiers.data))
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
      <QueryState
        isPending={isPending}
        isError={isError}
        loading={<SkeletonRows count={2} height="h-64" />}
        errorLabel="Couldn't load membership policies."
        label="Loading membership policies…"
        onRetry={() => {
          void policies.refetch()
          void tiers.refetch()
        }}
      >
        {policies.data && tiers.data ? (
          <TierGrid
            allTiers={tiers.data.memberships}
            data={policies.data}
            quotas={quotas.data ?? null}
          />
        ) : null}
      </QueryState>
      <TierFormDialog mode="create" open={creating} onClose={() => setCreating(false)} />
    </section>
  )
}
