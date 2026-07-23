import { Button } from '@/shared/ui'

type Props = {
  pending: boolean
  canSubmit: boolean
  onCancel: () => void
}

export function ScrapeDialogActions({ pending, canSubmit, onCancel }: Props) {
  return (
    <div className="flex justify-end gap-2 pt-2">
      <Button type="button" variant="ghost" disabled={pending} onClick={onCancel}>
        Cancel
      </Button>
      <Button type="submit" disabled={pending || !canSubmit}>
        {pending ? 'Starting…' : 'Start Scrape'}
      </Button>
    </div>
  )
}
