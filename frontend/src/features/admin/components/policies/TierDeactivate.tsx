import { useState } from 'react'
import type { AdminMembership } from '@/features/admin/api/memberships'
import { useDeactivateMembership } from '@/features/admin/hooks/useMemberships'

type Props = { tier: AdminMembership; allTiers: AdminMembership[] }

/** Deactivating a tier requires picking another active tier to migrate its users to. */
export function TierDeactivate({ tier, allTiers }: Props) {
  const others = allTiers.filter((t) => t.slug !== tier.slug && t.is_active)
  const [target, setTarget] = useState(others[0]?.slug ?? '')
  // Derived during render (not synced via effect): a refetch that changes
  // the tier set can leave `target` pointing at a slug no longer in
  // `others`, which would otherwise render a blank <select> while still
  // submitting the stale slug.
  const value = others.some((t) => t.slug === target) ? target : (others[0]?.slug ?? '')
  const deactivate = useDeactivateMembership()

  const onDeactivate = () => {
    if (!value) return
    const confirmed = window.confirm(
      `Deactivate ${tier.label}? ${tier.user_count} user(s) will move to ${value}.`,
    )
    if (confirmed) {
      deactivate.mutate({ slug: tier.slug, migrateTo: value })
    }
  }

  return (
    <span className="flex items-center gap-1">
      <select
        aria-label={`Migrate ${tier.label} users to`}
        className="rounded border border-border bg-background px-1 py-0.5"
        value={value}
        onChange={(event) => setTarget(event.target.value)}
      >
        {others.map((t) => (
          <option key={t.slug} value={t.slug}>
            {t.label}
          </option>
        ))}
      </select>
      <button
        type="button"
        className="underline disabled:opacity-50"
        disabled={!value}
        onClick={onDeactivate}
      >
        Deactivate
      </button>
      {deactivate.error ? (
        <span className="text-destructive">{deactivate.error.message}</span>
      ) : null}
    </span>
  )
}
