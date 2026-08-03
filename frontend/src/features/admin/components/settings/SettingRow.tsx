import type { EffectiveSetting } from '@/features/admin/api/settings'
import { useClearSetting } from '@/features/admin/hooks/useAdminSettings'
import { formatValue } from '@/features/admin/logic/settingValue'
import { Button, DataTableCell, DataTableRow, FormError, IconTooltip } from '@/shared/ui'

export function SettingRow({
  setting,
  onEdit,
}: {
  setting: EffectiveSetting
  onEdit: () => void
}) {
  const clear = useClearSetting()

  return (
    <DataTableRow>
      <DataTableCell>
        <KeyCell setting={setting} />
      </DataTableCell>
      <DataTableCell className="font-mono text-xs">
        {formatValue(setting.effective_value)}
      </DataTableCell>
      <DataTableCell className="font-mono text-xs text-muted-foreground" hideBelow="md">
        {formatValue(setting.env_value)}
      </DataTableCell>
      <DataTableCell>
        {setting.overridden ? (
          <span className="rounded bg-amber-500/15 px-1.5 py-0.5 text-xs text-amber-700">
            override
          </span>
        ) : (
          <span className="text-xs text-muted-foreground">env</span>
        )}
      </DataTableCell>
      <DataTableCell className="px-1.5">
        <div className="flex flex-wrap items-center justify-end gap-0.5">
          <Button
            type="button"
            variant="ghost"
            size="sm"
            className="h-6 px-1.5 text-[11px]"
            onClick={onEdit}
          >
            Edit
          </Button>
          {setting.overridden ? (
            <Button
              type="button"
              variant="ghost"
              size="sm"
              className="h-6 px-1.5 text-[11px]"
              title={`Env value will apply: ${formatValue(setting.env_value)}`}
              onClick={() => clear.mutate(setting.key)}
            >
              Clear
            </Button>
          ) : null}
        </div>
        <FormError error={clear.error} />
      </DataTableCell>
    </DataTableRow>
  )
}

function KeyCell({ setting }: { setting: EffectiveSetting }) {
  return (
    <div className="flex min-w-0 items-center gap-1.5">
      <span className="truncate font-mono text-xs">{setting.key}</span>
      {setting.description ? (
        <IconTooltip label={setting.description} side="top">
          <button
            type="button"
            className="inline-flex h-4 w-4 shrink-0 items-center justify-center rounded-full border border-border text-[10px] text-muted-foreground hover:bg-muted"
            aria-label={`About ${setting.key}`}
          >
            ?
          </button>
        </IconTooltip>
      ) : null}
    </div>
  )
}
