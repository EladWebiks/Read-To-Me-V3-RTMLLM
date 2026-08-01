import { useState } from 'react'
import type { EffectiveSetting } from '@/features/admin/api/settings'
import { useClearSetting } from '@/features/admin/hooks/useAdminSettings'
import { formatValue } from '@/features/admin/logic/settingValue'
import { FormError } from '@/shared/ui'
import { ValueEditor } from './ValueEditor'

export function SettingRow({ setting }: { setting: EffectiveSetting }) {
  const [editing, setEditing] = useState(false)
  const clear = useClearSetting()
  return (
    <tr className="border-t border-border/60 align-top">
      <td className="px-2 py-1.5 font-mono text-xs">{setting.key}</td>
      <td className="px-2 py-1.5 font-mono text-xs">
        {editing ? (
          <ValueEditor setting={setting} onDone={() => setEditing(false)} />
        ) : (
          formatValue(setting.effective_value)
        )}
      </td>
      <td className="px-2 py-1.5 font-mono text-xs text-muted-foreground">
        {formatValue(setting.env_value)}
      </td>
      <td className="px-2 py-1.5">
        {setting.overridden ? (
          <span className="rounded bg-amber-500/15 px-1.5 py-0.5 text-xs text-amber-600">
            override
          </span>
        ) : (
          <span className="text-xs text-muted-foreground">env</span>
        )}
      </td>
      <td className="px-2 py-1.5">
        {!editing && (
          <button
            type="button"
            className="text-xs underline"
            onClick={() => setEditing(true)}
          >
            Edit
          </button>
        )}
        {setting.overridden && (
          <button
            type="button"
            className="ml-2 text-xs underline"
            title={`Env value will apply: ${formatValue(setting.env_value)}`}
            onClick={() => clear.mutate(setting.key)}
          >
            Clear
          </button>
        )}
        <FormError error={clear.error} />
      </td>
    </tr>
  )
}
