import type { AdminUser } from '@/features/admin/api/users'
import { usePatchUser } from '@/features/admin/hooks/useAdminUsers'
import { Select } from '@/shared/ui'

export type MembershipOption = { slug: string; label: string }

export function MembershipSelect({
  user,
  memberships,
  patch,
}: {
  user: AdminUser
  memberships: MembershipOption[]
  patch: ReturnType<typeof usePatchUser>
}) {
  const options =
    memberships.length > 0
      ? memberships
      : [{ slug: user.membership, label: user.membership }]
  return (
    <Select
      size="sm"
      className="w-full max-w-[8.5rem]"
      value={user.membership}
      aria-label={`Membership for ${user.username} (operator override)`}
      onChange={(event) =>
        patch.mutate({ id: user.id, body: { membership: event.target.value } })
      }
    >
      {options.map((tier) => (
        <option key={tier.slug} value={tier.slug}>
          {tier.label}
        </option>
      ))}
    </Select>
  )
}
