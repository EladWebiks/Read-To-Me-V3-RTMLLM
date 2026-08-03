import { useState } from 'react'
import type { AdminMembership } from '@/features/admin/api/memberships'
import { usePatchMembership } from '@/features/admin/hooks/useMemberships'
import { FormError } from '@/shared/ui'
import { TierFormDialog } from './TierFormDialog'
import { TierHeaderActions } from './TierHeaderActions'

type Props = { tier: AdminMembership; allTiers: AdminMembership[] }

/** Card header: tier identity + rank/default/activation controls. */
export function TierActions({ tier, allTiers }: Props) {
  const [editing, setEditing] = useState(false)
  const patch = usePatchMembership()

  return (
    <div className="flex flex-wrap items-start justify-between gap-3">
      <TierIdentity tier={tier} error={patch.error} />
      <TierHeaderActions
        tier={tier}
        allTiers={allTiers}
        onEdit={() => setEditing(true)}
        onPatch={(body) => patch.mutate({ slug: tier.slug, patch: body })}
      />
      <TierFormDialog
        mode="edit"
        tier={tier}
        open={editing}
        onClose={() => setEditing(false)}
      />
    </div>
  )
}

function TierIdentity({ tier, error }: { tier: AdminMembership; error: Error | null }) {
  return (
    <div className="min-w-0 space-y-1">
      <div className="flex flex-wrap items-center gap-2">
        <h2 className="text-base font-semibold tracking-tight">{tier.label}</h2>
        {tier.price_label ? (
          <span className="text-sm text-muted-foreground">{tier.price_label}</span>
        ) : null}
        {tier.is_default ? (
          <span className="rounded-md bg-secondary px-1.5 py-0.5 text-[11px] font-medium">
            default
          </span>
        ) : null}
        {!tier.is_active ? (
          <span className="rounded-md bg-destructive/15 px-1.5 py-0.5 text-[11px] font-medium text-destructive">
            inactive
          </span>
        ) : null}
      </div>
      <p className="text-xs text-muted-foreground">
        <span className="font-mono text-[11px]">{tier.slug}</span>
        {' · '}
        {tier.user_count} user{tier.user_count === 1 ? '' : 's'}
        {' · '}
        rank {tier.rank}
      </p>
      <FormError error={error} />
    </div>
  )
}
