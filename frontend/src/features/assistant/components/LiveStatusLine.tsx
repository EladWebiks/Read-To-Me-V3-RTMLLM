/** Ephemeral in-turn status (thinking / tool) — not part of chat history. */
export function LiveStatusLine({ label }: { label: string }) {
  return (
    <div
      className="flex items-center gap-2 px-1 py-0.5 text-xs text-muted-foreground"
      aria-live="polite"
    >
      <span
        className="inline-block h-1.5 w-1.5 shrink-0 animate-pulse rounded-full bg-muted-foreground/70"
        aria-hidden
      />
      <span className="truncate">{label}</span>
    </div>
  )
}
