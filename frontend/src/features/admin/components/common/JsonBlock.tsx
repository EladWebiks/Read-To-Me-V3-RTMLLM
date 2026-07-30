export function JsonBlock({ label, value }: { label: string; value: unknown }) {
  if (value === null || value === undefined) {
    return <p className="text-xs text-muted-foreground">{label}: —</p>
  }
  return (
    <details className="text-xs">
      <summary className="cursor-pointer text-muted-foreground">{label}</summary>
      <pre className="mt-1 max-h-64 overflow-auto rounded bg-muted/40 p-2">
        {JSON.stringify(value, null, 2)}
      </pre>
    </details>
  )
}
