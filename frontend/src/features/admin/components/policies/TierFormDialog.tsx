import { useState, type ChangeEvent, type FormEvent } from 'react'
import type { AdminMembership } from '@/features/admin/api/memberships'
import {
  useCreateMembership,
  usePatchMembership,
} from '@/features/admin/hooks/useMemberships'
import { Dialog, DialogContent, DialogHeader, DialogTitle, FormError } from '@/shared/ui'
import { TierFormFields } from './TierFormFields'

type Props = ({ mode: 'create' } | { mode: 'edit'; tier: AdminMembership }) & {
  open: boolean
  onClose: () => void
}

export type TierDraft = {
  slug: string
  label: string
  rank: string
  description: string
  priceLabel: string
}

function draftFor(props: Props): TierDraft {
  if (props.mode === 'edit') {
    const { tier } = props
    return {
      slug: tier.slug,
      label: tier.label,
      rank: String(tier.rank),
      description: tier.description ?? '',
      priceLabel: tier.price_label ?? '',
    }
  }
  return { slug: '', label: '', rank: '0', description: '', priceLabel: '' }
}

/** Mounted only while the dialog is open, so re-opening always starts fresh. */
function TierForm(props: Props) {
  const { onClose, ...rest } = props
  const [draft, setDraft] = useState<TierDraft>(() => draftFor(props))
  const create = useCreateMembership()
  const patch = usePatchMembership()
  const mutation = rest.mode === 'create' ? create : patch
  const onChange =
    (key: keyof TierDraft) =>
    (event: ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) =>
      setDraft((prev) => ({ ...prev, [key]: event.target.value }))

  const onSubmit = (event: FormEvent) => {
    event.preventDefault()
    const body = {
      label: draft.label,
      rank: Number(draft.rank),
      description: draft.description === '' ? null : draft.description,
      price_label: draft.priceLabel === '' ? null : draft.priceLabel,
    }
    if (rest.mode === 'create') {
      create.mutate({ slug: draft.slug, ...body }, { onSuccess: onClose })
    } else {
      patch.mutate({ slug: rest.tier.slug, patch: body }, { onSuccess: onClose })
    }
  }

  return (
    <form className="space-y-3" onSubmit={onSubmit}>
      <TierFormFields
        showSlug={rest.mode === 'create'}
        draft={draft}
        onChange={onChange}
      />
      <FormError error={mutation.error} />
      <button
        type="submit"
        className="rounded-md bg-primary px-3 py-1.5 text-sm text-primary-foreground disabled:opacity-50"
        disabled={mutation.isPending}
      >
        {mutation.isPending ? 'Saving…' : 'Save'}
      </button>
    </form>
  )
}

export function TierFormDialog(props: Props) {
  const { open, onClose } = props
  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        if (!next) onClose()
      }}
    >
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{props.mode === 'create' ? 'New tier' : 'Edit tier'}</DialogTitle>
        </DialogHeader>
        {open ? <TierForm {...props} /> : null}
      </DialogContent>
    </Dialog>
  )
}
