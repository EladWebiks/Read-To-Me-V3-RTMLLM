import type {
  AdminMembership,
  MembershipPatchBody,
} from '@/features/admin/api/memberships'
import { Button } from '@/shared/ui'
import { TierDeactivate } from './TierDeactivate'

export function TierHeaderActions({
  tier,
  allTiers,
  onEdit,
  onPatch,
}: {
  tier: AdminMembership
  allTiers: AdminMembership[]
  onEdit: () => void
  onPatch: (body: MembershipPatchBody) => void
}) {
  return (
    <div className="flex flex-wrap items-center gap-1">
      <Button type="button" variant="outline" size="sm" onClick={onEdit}>
        Edit
      </Button>
      {!tier.is_default && tier.is_active ? (
        <Button
          type="button"
          variant="ghost"
          size="sm"
          onClick={() => onPatch({ is_default: true })}
        >
          Make default
        </Button>
      ) : null}
      {!tier.is_active ? (
        <Button
          type="button"
          variant="ghost"
          size="sm"
          onClick={() => onPatch({ is_active: true })}
        >
          Reactivate
        </Button>
      ) : null}
      {tier.is_active && !tier.is_default ? (
        <TierDeactivate tier={tier} allTiers={allTiers} />
      ) : null}
    </div>
  )
}
