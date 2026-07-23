import { X } from 'lucide-react'
import { Button } from '@/shared/ui'

export function AssistantPanelBody({ onClose }: { onClose: () => void }) {
  return (
    <>
      <header className="flex items-center justify-between border-b border-border px-4 py-3">
        <div>
          <p className="text-sm font-semibold">Assistant</p>
          <p className="text-xs text-muted-foreground">App-wide · Milestone B</p>
        </div>
        <Button
          type="button"
          variant="ghost"
          size="icon"
          aria-label="Close assistant"
          onClick={onClose}
        >
          <X className="h-4 w-4" />
        </Button>
      </header>
      <div className="flex min-h-48 flex-1 flex-col justify-center gap-2 px-4 py-6 text-sm leading-relaxed text-muted-foreground">
        <p>Chat will live here once the LLM tools land.</p>
        <p>Not tied to a book or chapter — library, scrape, and read via tools.</p>
      </div>
      <div className="border-t border-border p-3">
        <div
          aria-disabled="true"
          className="rounded-md border border-dashed border-border bg-muted/40 px-3 py-2 text-sm text-muted-foreground"
        >
          Ask anything about your library…
        </div>
      </div>
    </>
  )
}
