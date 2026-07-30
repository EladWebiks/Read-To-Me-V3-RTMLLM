import { useAdminSettings } from '@/features/admin/hooks/useAdminSettings'
import { SettingRow } from './SettingRow'

export function SettingsPage() {
  const { data, isLoading, error } = useAdminSettings()
  if (isLoading) {
    return <p className="text-sm text-muted-foreground">Loading settings…</p>
  }
  if (error || !data) {
    return <p className="text-sm text-destructive">Failed to load settings.</p>
  }
  return (
    <section>
      <h1 className="mb-1 text-lg font-semibold">Runtime settings</h1>
      <p className="mb-4 text-sm text-muted-foreground">
        Overrides apply without a restart (other processes converge within ~30s). Clearing
        an override restores the environment value.
      </p>
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
    </section>
  )
}
