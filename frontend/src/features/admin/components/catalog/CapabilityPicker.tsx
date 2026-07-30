import { MODEL_CAPABILITIES } from '@/features/admin/api/catalog'

export function CapabilityPicker({
  selected,
  onToggle,
}: {
  selected: string[]
  onToggle: (capability: string) => void
}) {
  return (
    <fieldset className="flex flex-wrap gap-x-4 gap-y-1 text-xs">
      <legend className="mb-1 text-muted-foreground">Capabilities</legend>
      {MODEL_CAPABILITIES.map((capability) => (
        <label key={capability} className="flex items-center gap-1">
          <input
            type="checkbox"
            checked={selected.includes(capability)}
            onChange={() => onToggle(capability)}
          />
          {capability}
        </label>
      ))}
    </fieldset>
  )
}
