import { useState, type ReactNode } from 'react'
import type {
  MembershipPolicy,
  PolicyPatch,
} from '@/features/admin/api/membershipPolicies'
import { usePatchMembershipPolicy } from '@/features/admin/hooks/useMembershipPolicies'
import { parsePolicyInput, POLICY_FIELDS } from '@/features/admin/logic/policyFields'
import { FormError } from '@/shared/ui'
import { PolicyField } from './PolicyField'

type Props = {
  policy: MembershipPolicy
  inherited: Record<string, number>
  header?: ReactNode
  children?: ReactNode
}

function initialDrafts(policy: MembershipPolicy): Record<string, string> {
  return Object.fromEntries(
    POLICY_FIELDS.map((f) => [
      f.key,
      policy[f.key] === null ? '' : String(policy[f.key]),
    ]),
  )
}

/** Returns the changed fields, or null when any input is invalid. */
function buildPatch(
  policy: MembershipPolicy,
  drafts: Record<string, string>,
): PolicyPatch | null {
  const patch: PolicyPatch = {}
  for (const field of POLICY_FIELDS) {
    const parsed = parsePolicyInput(drafts[field.key] ?? '')
    if (parsed === undefined) return null
    if (parsed !== (policy[field.key] ?? null)) patch[field.key] = parsed
  }
  return patch
}

export function PolicyCard({ policy, inherited, header, children }: Props) {
  const [drafts, setDrafts] = useState(() => initialDrafts(policy))
  const [invalid, setInvalid] = useState(false)
  const mutation = usePatchMembershipPolicy()

  const onSave = () => {
    const patch = buildPatch(policy, drafts)
    setInvalid(patch === null)
    if (patch === null) return
    if (Object.keys(patch).length > 0) {
      mutation.mutate({ membership: policy.membership, patch })
    }
  }

  return (
    <div className="rounded-lg border border-border p-4">
      {header ?? <h2 className="mb-2 font-medium capitalize">{policy.membership}</h2>}
      <div className="grid gap-2 sm:grid-cols-2">
        {POLICY_FIELDS.map((meta) => (
          <PolicyField
            key={meta.key}
            membership={policy.membership}
            meta={meta}
            value={drafts[meta.key] ?? ''}
            inherited={inherited}
            onChange={(raw) => setDrafts((prev) => ({ ...prev, [meta.key]: raw }))}
          />
        ))}
      </div>
      <FormError className="mt-2" error={invalid ? 'Enter numbers (or blank).' : null} />
      <button
        type="button"
        className="mt-3 rounded-md bg-primary px-3 py-1.5 text-sm text-primary-foreground disabled:opacity-50"
        disabled={mutation.isPending}
        onClick={onSave}
      >
        {mutation.isPending ? 'Saving…' : 'Save'}
      </button>
      <FormError className="mt-2" error={mutation.error} />
      {children}
    </div>
  )
}
