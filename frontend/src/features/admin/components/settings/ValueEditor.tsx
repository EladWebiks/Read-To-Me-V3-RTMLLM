import { useState } from 'react'
import type { EffectiveSetting } from '@/features/admin/api/settings'
import { useSetSetting } from '@/features/admin/hooks/useAdminSettings'
import { formatValue, parseValue } from '@/features/admin/logic/settingValue'

export function ValueEditor({
  setting,
  onDone,
}: {
  setting: EffectiveSetting
  onDone: () => void
}) {
  const [text, setText] = useState(formatValue(setting.effective_value))
  const save = useSetSetting()

  const submit = () => {
    save.mutate({ key: setting.key, value: parseValue(text) }, { onSuccess: onDone })
  }

  return (
    <div className="flex flex-col gap-1">
      <input
        className="w-48 rounded border border-border bg-background px-1.5 py-0.5 font-mono text-xs"
        value={text}
        onChange={(event) => setText(event.target.value)}
        aria-label={`Value for ${setting.key}`}
      />
      <div className="flex gap-2">
        <button
          type="button"
          className="text-xs underline"
          onClick={submit}
          disabled={save.isPending}
        >
          Save
        </button>
        <button type="button" className="text-xs underline" onClick={onDone}>
          Cancel
        </button>
      </div>
      {save.error ? (
        <p className="text-xs text-destructive">{save.error.message}</p>
      ) : null}
    </div>
  )
}
