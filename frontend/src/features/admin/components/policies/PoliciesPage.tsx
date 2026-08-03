import { useState } from 'react'
import { useMemberships } from '@/features/admin/hooks/useMemberships'
import { useMembershipPolicies } from '@/features/admin/hooks/useMembershipPolicies'
import { useMembershipQuotas } from '@/features/admin/hooks/useMembershipQuotas'
import { Button, QueryState, SkeletonRows } from '@/shared/ui'
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
    <section className="space-y-4 animate-fade-in-up">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="space-y-1">
          <h1 className="text-xl font-semibold tracking-tight">Memberships</h1>
          <p className="max-w-2xl text-sm text-muted-foreground">
            Caps and quotas per tier. Changes apply on the user&apos;s next turn — no
            restart.
          </p>
        </div>
        <Button type="button" size="sm" onClick={() => setCreating(true)}>
          New tier
        </Button>
      </div>
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
