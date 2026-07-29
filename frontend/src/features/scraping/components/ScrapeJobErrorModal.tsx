import { Button, Dialog, DialogContent, DialogHeader, DialogTitle } from '@/shared/ui'

type Props = {
  open: boolean
  onClose: () => void
  detail: string
}

/** Modal with the full scrape failure text. */
export function ScrapeJobErrorModal({ open, onClose, detail }: Props) {
  return (
    <Dialog open={open} onOpenChange={(v) => !v && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Scrape error</DialogTitle>
        </DialogHeader>
        <p className="whitespace-pre-wrap break-words text-sm text-muted-foreground">
          {detail}
        </p>
        <div className="mt-4 flex justify-end">
          <Button type="button" variant="outline" size="sm" onClick={onClose}>
            Close
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  )
}
