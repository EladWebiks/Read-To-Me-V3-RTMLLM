import type { ReactNode, Ref } from 'react'

type Props = {
  sectionRef: Ref<HTMLElement | null>
  slotRef: Ref<HTMLDivElement | null>
  title: string
  description?: string
  toolbar?: ReactNode
  children: ReactNode
  footer: ReactNode
}

/**
 * Viewport-friendly list page chrome: title, optional toolbar, measured slot, pinned footer.
 * Pair with useDataListLayout — do not lock the whole app shell.
 */
export function DataListFrame({
  sectionRef,
  slotRef,
  title,
  description,
  toolbar,
  children,
  footer,
}: Props) {
  return (
    <section
      ref={sectionRef}
      className="flex flex-col gap-3 overflow-hidden animate-fade-in-up"
    >
      <div className="shrink-0 space-y-1">
        <h1 className="text-xl font-semibold tracking-tight">{title}</h1>
        {description ? (
          <p className="max-w-2xl text-sm text-muted-foreground">{description}</p>
        ) : null}
      </div>
      {toolbar ? <div className="shrink-0">{toolbar}</div> : null}
      <div ref={slotRef} className="min-h-0 flex-1 overflow-hidden">
        {children}
      </div>
      <div className="shrink-0 border-t border-border/60 pt-2">{footer}</div>
    </section>
  )
}
