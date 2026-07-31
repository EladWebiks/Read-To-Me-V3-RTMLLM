import { useState } from 'react'
import type { AdminMembership } from '@/features/admin/api/memberships'
import { usePatchMembership } from '@/features/admin/hooks/useMemberships'
import { TierFormDialog } from './TierFormDialog'
import { TierDeactivate } from './TierDeactivate'

type Props = { tier: AdminMembership; allTiers: AdminMembership[] }

/** Card header: tier identity + rank/default/activation controls. */
export function TierActions({ tier, allTiers }: Props) {
  const [editing, setEditing] = useState(false)
  const patch = usePatchMembership()

  return (
    <div className="mb-2">
      <div className="flex flex-wrap items-center gap-2">
        <h2 className="font-medium">{tier.label}</h2>
        {tier.price_label ? (
          <span className="text-xs text-muted-foreground">{tier.price_label}</span>
        ) : null}
        {tier.is_default ? (
          <span className="rounded bg-secondary px-1.5 py-0.5 text-xs">default</span>
        ) : null}
        {!tier.is_active ? (
          <span className="rounded bg-destructive/20 px-1.5 py-0.5 text-xs text-destructive">
            inactive
          </span>
        ) : null}
      </div>
      <div className="mt-1 flex flex-wrap items-center gap-2 text-xs">
        <button type="button" className="underline" onClick={() => setEditing(true)}>
          Edit
        </button>
        {!tier.is_default ? (
          <button
            type="button"
            className="underline"
            onClick={() => patch.mutate({ slug: tier.slug, patch: { is_default: true } })}
          >
            Make default
          </button>
        ) : null}
        {!tier.is_active ? (
          <button
            type="button"
            className="underline"
            onClick={() => patch.mutate({ slug: tier.slug, patch: { is_active: true } })}
          >
            Reactivate
          </button>
        ) : null}
        {tier.is_active && !tier.is_default ? (
          <TierDeactivate tier={tier} allTiers={allTiers} />
        ) : null}
      </div>
      {patch.error ? (
        <p className="text-xs text-destructive">{patch.error.message}</p>
      ) : null}
      <TierFormDialog
        mode="edit"
        tier={tier}
        open={editing}
        onClose={() => setEditing(false)}
      />
    </div>
  )
}
