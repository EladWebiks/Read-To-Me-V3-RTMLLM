import type { DownloadProvider } from '@/features/downloads/types'
import { Select } from '@/shared/ui'

export function ProviderSelect({
  value,
  onChange,
}: {
  value: DownloadProvider
  onChange: (value: DownloadProvider) => void
}) {
  return (
    <label className="flex items-center gap-1">
      Provider
      <Select
        className="w-auto"
        value={value}
        onChange={(event) => onChange(event.target.value as DownloadProvider)}
      >
        <option value="edge">Edge</option>
        <option value="sapi">SAPI</option>
      </Select>
    </label>
  )
}

export function NumField({
  label,
  value,
  min,
  max,
  onChange,
}: {
  label: string
  value: number
  min: number
  max: number
  onChange: (value: number) => void
}) {
  return (
    <label className="flex items-center gap-1">
      {label}
      <input
        type="number"
        className="w-20 rounded-md border border-border bg-background px-2 py-1 text-foreground"
        value={value}
        min={min}
        max={max}
        onChange={(event) => onChange(Number(event.target.value))}
      />
    </label>
  )
}
