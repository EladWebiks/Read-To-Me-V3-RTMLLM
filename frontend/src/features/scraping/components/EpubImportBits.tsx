import { Check } from 'lucide-react'
import { Label } from '@/shared/ui'
import type { EpubImportResult } from '../types/importTypes'

export function EpubField(props: {
  label: string
  hint?: string
  children: React.ReactNode
}) {
  return (
    <div className="space-y-1">
      <Label className="text-xs text-muted-foreground">{props.label}</Label>
      {props.children}
      {props.hint ? (
        <p className="text-[11px] text-muted-foreground">{props.hint}</p>
      ) : null}
    </div>
  )
}

export function EpubImportSuccess({ result }: { result: EpubImportResult }) {
  return (
    <div className="space-y-3 rounded-md border border-emerald-500/25 bg-emerald-500/10 px-4 py-4">
      <div className="flex items-start gap-3">
        <span className="mt-0.5 flex size-7 shrink-0 items-center justify-center rounded-full bg-emerald-500/20 text-emerald-600">
          <Check className="size-4" strokeWidth={2.5} />
        </span>
        <div className="min-w-0 space-y-1">
          <p className="text-sm font-medium text-foreground">
            Imported {result.chapters_imported} chapters
          </p>
          <p className="truncate text-sm text-muted-foreground" title={result.book_title}>
            {result.book_title}
            {result.author ? ` · ${result.author}` : ''}
          </p>
        </div>
      </div>
      {result.files.length > 1 ? (
        <ul className="space-y-1 border-t border-emerald-500/20 pt-3 text-xs text-muted-foreground">
          {result.files.map((f, i) => (
            <li key={f.name} className="flex justify-between gap-2">
              <span className="min-w-0 truncate" title={f.name}>
                Part {i + 1}
              </span>
              <span className="shrink-0 tabular-nums">{f.chapters} ch</span>
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  )
}
