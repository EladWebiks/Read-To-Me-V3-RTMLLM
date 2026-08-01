import { useState } from 'react'
import type { EffectiveSetting } from '@/features/admin/api/settings'
import { useSetSetting } from '@/features/admin/hooks/useAdminSettings'
import { formatValue, parseValue } from '@/features/admin/logic/settingValue'
import { FormError, Input } from '@/shared/ui'

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
      <Input
        size="sm"
        className="w-48 font-mono"
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
      <FormError error={save.error} />
    </div>
  )
}
