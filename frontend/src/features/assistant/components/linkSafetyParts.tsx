import { Copy, ExternalLink } from 'lucide-react'
import { Button } from '@/shared/ui'

export function LinkSafetyHeader({ title, warning }: { title: string; warning: string }) {
  return (
    <div className="mb-3 flex items-start gap-2 pe-8">
      <ExternalLink className="mt-0.5 h-5 w-5 shrink-0 text-muted-foreground" />
      <div>
        <h2 id="ext-link-title" className="text-base font-semibold text-foreground">
          {title}
        </h2>
        <p className="mt-1 text-sm text-muted-foreground">{warning}</p>
      </div>
    </div>
  )
}

export function LinkSafetyActions(props: {
  copyLabel: string
  openLabel: string
  onCopy: () => void
  onOpen: () => void
}) {
  return (
    <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
      <Button
        type="button"
        variant="outline"
        size="sm"
        className="gap-1.5"
        onClick={props.onCopy}
      >
        <Copy className="h-3.5 w-3.5" />
        {props.copyLabel}
      </Button>
      <Button type="button" size="sm" className="gap-1.5" onClick={props.onOpen}>
        <ExternalLink className="h-3.5 w-3.5" />
        {props.openLabel}
      </Button>
    </div>
  )
}
