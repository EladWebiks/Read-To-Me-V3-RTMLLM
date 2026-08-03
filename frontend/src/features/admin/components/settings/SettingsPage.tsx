import { useState } from 'react'
import type { EffectiveSetting } from '@/features/admin/api/settings'
import { useAdminSettings } from '@/features/admin/hooks/useAdminSettings'
import {
  DataTable,
  DataTableBody,
  DataTableColumn,
  DataTableHeader,
  QueryState,
  SkeletonTable,
  TooltipProvider,
} from '@/shared/ui'
import { SettingEditDialog } from './SettingEditDialog'
import { SettingRow } from './SettingRow'

export function SettingsPage() {
  const { data, isLoading, error, refetch } = useAdminSettings()
  const [editing, setEditing] = useState<EffectiveSetting | null>(null)

  return (
    <section className="space-y-4 animate-fade-in-up">
      <div className="space-y-1">
        <h1 className="text-xl font-semibold tracking-tight">Runtime settings</h1>
        <p className="max-w-2xl text-sm text-muted-foreground">
          Overrides apply without a restart (other processes converge within ~30s).
          Clearing an override restores the environment value.
        </p>
      </div>
      <QueryState
        isPending={isLoading}
        isError={Boolean(error) || (!isLoading && !data)}
        loading={<SkeletonTable rows={10} cols={5} />}
        errorLabel="Couldn't load settings."
        label="Loading settings…"
        onRetry={() => void refetch()}
      >
        {data ? (
          <TooltipProvider>
            <DataTable
              empty={data.settings.length === 0}
              emptyLabel="No tunable settings."
            >
              <DataTableHeader>
                <DataTableColumn>Key</DataTableColumn>
                <DataTableColumn>Effective</DataTableColumn>
                <DataTableColumn hideBelow="md">Env</DataTableColumn>
                <DataTableColumn className="w-24">Status</DataTableColumn>
                <DataTableColumn className="w-28" srOnly>
                  Actions
                </DataTableColumn>
              </DataTableHeader>
              <DataTableBody>
                {data.settings.map((setting) => (
                  <SettingRow
                    key={setting.key}
                    setting={setting}
                    onEdit={() => setEditing(setting)}
                  />
                ))}
              </DataTableBody>
            </DataTable>
          </TooltipProvider>
        ) : null}
      </QueryState>
      {editing ? (
        <SettingEditDialog
          setting={editing}
          open
          onOpenChange={(open) => {
            if (!open) setEditing(null)
          }}
        />
      ) : null}
    </section>
  )
}
