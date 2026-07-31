import type { ChangeEvent } from 'react'
import { Input, Label } from '@/shared/ui'
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
        <div className="space-y-1">
          <Label htmlFor="tier-slug">Slug</Label>
          <Input
            id="tier-slug"
            value={draft.slug}
            pattern="^[a-z0-9_-]{1,32}$"
            title="Lowercase letters, digits, _ or -, up to 32 characters"
            onChange={onChange('slug')}
            required
          />
        </div>
      ) : null}
      <div className="space-y-1">
        <Label htmlFor="tier-label">Label</Label>
        <Input
          id="tier-label"
          value={draft.label}
          onChange={onChange('label')}
          required
        />
      </div>
      <div className="space-y-1">
        <Label htmlFor="tier-rank">Rank</Label>
        <Input
          id="tier-rank"
          type="number"
          value={draft.rank}
          onChange={onChange('rank')}
          required
        />
      </div>
      <div className="space-y-1">
        <Label htmlFor="tier-description">Description</Label>
        <textarea
          id="tier-description"
          className="flex w-full rounded-md border border-border bg-background px-3 py-1.5 text-sm shadow-sm"
          value={draft.description}
          onChange={onChange('description')}
        />
      </div>
      <div className="space-y-1">
        <Label htmlFor="tier-price">Price label</Label>
        <Input
          id="tier-price"
          value={draft.priceLabel}
          onChange={onChange('priceLabel')}
        />
      </div>
    </>
  )
}
