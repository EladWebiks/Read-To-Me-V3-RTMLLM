import type { ChangeEvent } from 'react'
import { FormField, TextField } from '@/shared/ui'
import type { TierDraft } from './TierFormDialog'

type Props = {
  showSlug: boolean
  draft: TierDraft
  onChange: (
    key: keyof TierDraft,
  ) => (event: ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => void
}

/** The bare input fields for TierFormDialog's form (slug is create-only). */
export function TierFormFields({ showSlug, draft, onChange }: Props) {
  return (
    <>
      {showSlug ? (
        <TextField
          id="tier-slug"
          label="Slug"
          value={draft.slug}
          pattern="^[a-z0-9_-]{1,32}$"
          title="Lowercase letters, digits, _ or -, up to 32 characters"
          onChange={onChange('slug')}
          required
        />
      ) : null}
      <TextField
        id="tier-label"
        label="Label"
        value={draft.label}
        onChange={onChange('label')}
        required
      />
      <TextField
        id="tier-rank"
        label="Rank"
        type="number"
        value={draft.rank}
        onChange={onChange('rank')}
        required
      />
      <FormField id="tier-description" label="Description">
        <textarea
          id="tier-description"
          className="flex w-full rounded-md border border-border bg-background px-3 py-1.5 text-sm shadow-sm"
          value={draft.description}
          onChange={onChange('description')}
        />
      </FormField>
      <TextField
        id="tier-price"
        label="Price label"
        value={draft.priceLabel}
        onChange={onChange('priceLabel')}
      />
    </>
  )
}
