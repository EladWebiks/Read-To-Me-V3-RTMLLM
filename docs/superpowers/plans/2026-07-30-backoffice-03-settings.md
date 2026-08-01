# Backoffice 03 — Settings Screen Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Frontend-only settings screen over the existing `/api/admin/settings` API: table of whitelisted keys (effective value, env value, override status), set an override (PUT), clear one (DELETE, showing the env value that will apply), with typed API errors surfaced inline.

**Architecture:** Zero backend work. `features/admin` gains a settings API module, react-query hooks, and three small components; the route swaps its `AdminPlaceholder`. TS types mirror `EffectiveSettingRead` exactly.

**Tech Stack:** React 19, react-query, vitest + Testing Library.

**Spec:** `docs/superpowers/specs/2026-07-30-backoffice-mvp-design.md`. **Depends on:** `2026-07-30-backoffice-01-foundation.md` (routes/guard, `ApiError` detail parsing).

## Global Constraints

- Frontend gates (run from `frontend/`): `npm run lint`, `npm run build`, `npm run test`.
- Commit with `bash scripts/git-commit-clean.sh /tmp/msg.txt`. **Never** add attribution trailers. Verify with `git log -1 --format=%B`.
- ESLint limits: file ≤110 lines, function ≤60, nesting ≤3 (tests/barrels exempt).
- All server state via react-query; all fetching through `src/shared/lib/api.ts`; mirror backend response schemas exactly — never reshape.
- The settings API only serves whitelisted tunables (no secrets by construction).

---

### Task 1: Settings screen

**Files:**
- Create: `frontend/src/features/admin/api/settings.ts`
- Create: `frontend/src/features/admin/hooks/useAdminSettings.ts`
- Create: `frontend/src/features/admin/logic/settingValue.ts`
- Create: `frontend/src/features/admin/components/settings/SettingsPage.tsx`
- Create: `frontend/src/features/admin/components/settings/SettingRow.tsx`
- Create: `frontend/src/features/admin/components/settings/ValueEditor.tsx`
- Modify: `frontend/src/features/admin/index.ts`
- Modify: `frontend/src/app/App.tsx` (swap the settings placeholder)
- Test: `frontend/src/features/admin/logic/settingValue.test.ts`
- Test: `frontend/src/features/admin/components/settings/SettingsPage.test.tsx`

**Interfaces:**
- Consumes: existing `GET/PUT/DELETE /api/admin/settings[/{key}]`; foundation's `apiGet`/`apiPut`/`apiDelete` + `ApiError` (message carries the backend `detail`).
- Produces: `SettingsPage` export; `EffectiveSetting` type mirroring `EffectiveSettingRead` exactly (`key`, `effective_value`, `env_value`, `overridden`, `updated_by?`, `updated_at?`).

- [x] **Step 1: Write the failing tests**

```typescript
// frontend/src/features/admin/logic/settingValue.test.ts
import { describe, expect, it } from 'vitest'
import { formatValue, parseValue } from './settingValue'

describe('settingValue', () => {
  it('round-trips JSON scalars', () => {
    expect(parseValue('3')).toBe(3)
    expect(parseValue('true')).toBe(true)
    expect(parseValue('"internal_only"')).toBe('internal_only')
    expect(formatValue(3)).toBe('3')
    expect(formatValue('internal_only')).toBe('"internal_only"')
  })

  it('treats unquoted text as a plain string', () => {
    expect(parseValue('internal_only')).toBe('internal_only')
  })
})
```

```tsx
// frontend/src/features/admin/components/settings/SettingsPage.test.tsx
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { SettingsPage } from './SettingsPage'
import {
  deleteAdminSetting,
  fetchAdminSettings,
  putAdminSetting,
} from '@/features/admin/api/settings'
import { ApiError } from '@/shared/lib/api'

vi.mock('@/features/admin/api/settings', () => ({
  fetchAdminSettings: vi.fn(),
  putAdminSetting: vi.fn(),
  deleteAdminSetting: vi.fn(),
}))

const SETTINGS = {
  settings: [
    { key: 'llm_runtime.max_tool_iters', effective_value: 8, env_value: 5, overridden: true },
    { key: 'scrape.delay_seconds', effective_value: 1.5, env_value: 1.5, overridden: false },
  ],
}

function renderPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={queryClient}>
      <SettingsPage />
    </QueryClientProvider>,
  )
}

describe('SettingsPage', () => {
  it('lists keys with override status', async () => {
    vi.mocked(fetchAdminSettings).mockResolvedValue(SETTINGS)
    renderPage()
    expect(await screen.findByText('llm_runtime.max_tool_iters')).toBeTruthy()
    expect(screen.getByText('override')).toBeTruthy()
    expect(vi.mocked(deleteAdminSetting)).not.toHaveBeenCalled()
  })

  it('saves an edited value as typed JSON', async () => {
    vi.mocked(fetchAdminSettings).mockResolvedValue(SETTINGS)
    vi.mocked(putAdminSetting).mockResolvedValue({
      key: 'llm_runtime.max_tool_iters',
      value: 9,
      updated_by: 'u1',
      updated_at: '2026-07-30T00:00:00Z',
    })
    renderPage()
    fireEvent.click((await screen.findAllByText('Edit'))[0])
    fireEvent.change(screen.getByLabelText('Value for llm_runtime.max_tool_iters'), {
      target: { value: '9' },
    })
    fireEvent.click(screen.getByText('Save'))
    expect(putAdminSetting).toHaveBeenCalledWith('llm_runtime.max_tool_iters', 9)
  })

  it('shows the API detail inline when the save is rejected', async () => {
    vi.mocked(fetchAdminSettings).mockResolvedValue(SETTINGS)
    vi.mocked(putAdminSetting).mockRejectedValue(new ApiError(422, 'value must be >= 1'))
    renderPage()
    fireEvent.click((await screen.findAllByText('Edit'))[0])
    fireEvent.click(screen.getByText('Save'))
    expect(await screen.findByText('value must be >= 1')).toBeTruthy()
  })
})
```

- [x] **Step 2: Run tests to verify they fail**

Run (from `frontend/`): `npm run test -- settingValue SettingsPage`
Expected: FAIL — modules not found.

- [x] **Step 3: Implement logic + API + hooks**

```typescript
// frontend/src/features/admin/logic/settingValue.ts
/** Values are whitelisted JSON scalars/lists; edit them as JSON text. */
export function formatValue(value: unknown): string {
  return value === undefined ? '' : JSON.stringify(value)
}

/** JSON when it parses; otherwise treat the raw text as a plain string. */
export function parseValue(text: string): unknown {
  const trimmed = text.trim()
  try {
    return JSON.parse(trimmed) as unknown
  } catch {
    return trimmed
  }
}
```

```typescript
// frontend/src/features/admin/api/settings.ts
import { apiDelete, apiGet, apiPut } from '@/shared/lib/api'

/** Mirrors EffectiveSettingRead (runtime_config/schemas.py) exactly. */
export type EffectiveSetting = {
  key: string
  effective_value: unknown
  env_value: unknown
  overridden: boolean
  updated_by?: string | null
  updated_at?: string | null
}

export type SettingsListResponse = { settings: EffectiveSetting[] }

export type OverrideRead = {
  key: string
  value: unknown
  updated_by: string
  updated_at: string
}

export function fetchAdminSettings(): Promise<SettingsListResponse> {
  return apiGet('/api/admin/settings')
}

export function putAdminSetting(key: string, value: unknown): Promise<OverrideRead> {
  return apiPut(`/api/admin/settings/${encodeURIComponent(key)}`, { value })
}

export function deleteAdminSetting(key: string): Promise<void> {
  return apiDelete(`/api/admin/settings/${encodeURIComponent(key)}`)
}
```

```typescript
// frontend/src/features/admin/hooks/useAdminSettings.ts
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  deleteAdminSetting,
  fetchAdminSettings,
  putAdminSetting,
} from '@/features/admin/api/settings'

export const adminSettingsKey = ['admin', 'settings'] as const

export function useAdminSettings() {
  return useQuery({ queryKey: adminSettingsKey, queryFn: fetchAdminSettings })
}

export function useSetSetting() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ key, value }: { key: string; value: unknown }) =>
      putAdminSetting(key, value),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: adminSettingsKey }),
  })
}

export function useClearSetting() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: deleteAdminSetting,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: adminSettingsKey }),
  })
}
```

- [x] **Step 4: Implement the components**

```tsx
// frontend/src/features/admin/components/settings/SettingsPage.tsx
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
        Overrides apply without a restart (other processes converge within ~30s). Clearing an
        override restores the environment value.
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
```

```tsx
// frontend/src/features/admin/components/settings/SettingRow.tsx
import { useState } from 'react'
import type { EffectiveSetting } from '@/features/admin/api/settings'
import { useClearSetting } from '@/features/admin/hooks/useAdminSettings'
import { formatValue } from '@/features/admin/logic/settingValue'
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
          <button type="button" className="text-xs underline" onClick={() => setEditing(true)}>
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
        {clear.error ? <p className="text-xs text-destructive">{clear.error.message}</p> : null}
      </td>
    </tr>
  )
}
```

```tsx
// frontend/src/features/admin/components/settings/ValueEditor.tsx
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
      {save.error ? <p className="text-xs text-destructive">{save.error.message}</p> : null}
    </div>
  )
}
```

- [x] **Step 5: Wire the route and barrel**

Append to `frontend/src/features/admin/index.ts`:

```typescript
export { SettingsPage } from './components/settings/SettingsPage'
```

In `frontend/src/app/App.tsx`: extend the `@/features/admin` import with `SettingsPage` and change the settings route to:

```tsx
<Route path="settings" element={<SettingsPage />} />
```

- [x] **Step 6: Run tests to verify they pass**

Run: `npm run test -- settingValue SettingsPage`
Expected: PASS (5 tests)

- [x] **Step 7: Gates + commit**

```bash
cd frontend && npm run lint && npm run build && npm run test && cd ..
printf 'feat: add backoffice runtime-settings screen\n' > /tmp/msg.txt
git add -A
bash scripts/git-commit-clean.sh /tmp/msg.txt
git log -1 --format=%B
```
