import { useAdminSettings } from '@/features/admin/hooks/useAdminSettings'
import { QueryState, SkeletonTable } from '@/shared/ui'
import { SettingRow } from './SettingRow'

export function SettingsPage() {
  const { data, isLoading, error, refetch } = useAdminSettings()
  return (
    <section>
      <h1 className="mb-1 text-lg font-semibold">Runtime settings</h1>
      <p className="mb-4 text-sm text-muted-foreground">
        Overrides apply without a restart (other processes converge within ~30s). Clearing
        an override restores the environment value.
      </p>
      <QueryState
        isPending={isLoading}
        isError={Boolean(error) || (!isLoading && !data)}
        loading={<SkeletonTable rows={10} cols={5} />}
        errorLabel="Couldn't load settings."
        label="Loading settings…"
        onRetry={() => void refetch()}
      >
        {data ? (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="text-muted-foreground">
                <tr>
                  <th className="px-2 py-1.5 font-medium">Key</th>
                  <th className="px-2 py-1.5 font-medium">Effective</th>
                  <th className="px-2 py-1.5 font-medium">Env</th>
                  <th className="px-2 py-1.5 font-medium">Status</th>
                  <th className="px-2 py-1.5 font-medium">Actions</th>
                </tr>
              </thead>
              <tbody>
                {data.settings.map((setting) => (
                  <SettingRow key={setting.key} setting={setting} />
                ))}
              </tbody>
            </table>
          </div>
        ) : null}
      </QueryState>
    </section>
  )
}
