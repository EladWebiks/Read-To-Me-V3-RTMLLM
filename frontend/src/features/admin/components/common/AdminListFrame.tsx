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

/** Viewport-locked admin list: header + optional toolbar + table slot + pinned footer. */
export function AdminListFrame({
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
      className="flex h-full min-h-0 flex-col gap-3 overflow-hidden animate-fade-in-up"
    >
      <div className="shrink-0">
        <h1 className="text-lg font-semibold tracking-tight">{title}</h1>
        {description ? (
          <p className="mt-1 text-sm text-muted-foreground">{description}</p>
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
