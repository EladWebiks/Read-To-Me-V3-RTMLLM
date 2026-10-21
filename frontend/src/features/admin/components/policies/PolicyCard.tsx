import { useState, type ReactNode } from 'react'
import type {
  MembershipPolicy,
  PolicyPatch,
} from '@/features/admin/api/membershipPolicies'
import { usePatchMembershipPolicy } from '@/features/admin/hooks/useMembershipPolicies'
import { parsePolicyInput, POLICY_FIELDS } from '@/features/admin/logic/policyFields'
import { Button, FormError } from '@/shared/ui'
import { PolicyField } from './PolicyField'
import { SectionHeading } from './SectionHeading'

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
    <article className="overflow-hidden rounded-xl border border-border bg-card shadow-sm">
      <div className="border-b border-border/70 bg-muted/30 px-4 py-3">{header}</div>
      <div className="space-y-5 p-4 sm:p-5">
        <section className="space-y-3">
          <SectionHeading
            title="Per-turn caps"
            hint="Blank inherits the runtime default shown in the field."
          />
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
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
          <div className="flex flex-wrap items-center gap-3 pt-1">
            <Button
              type="button"
              size="sm"
              disabled={mutation.isPending}
              onClick={onSave}
            >
              {mutation.isPending ? 'Saving…' : 'Save caps'}
            </Button>
            <FormError error={invalid ? 'Enter numbers (or blank).' : null} />
            <FormError error={mutation.error} />
          </div>
        </section>
        {children}
      </div>
    </article>
  )
}
