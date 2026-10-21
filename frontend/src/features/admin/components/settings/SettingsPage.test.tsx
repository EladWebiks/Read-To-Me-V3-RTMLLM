import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
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
    {
      key: 'llm_runtime.max_tool_iters',
      effective_value: 8,
      env_value: 5,
      overridden: true,
      description: 'Max tool-calling iterations allowed in one assistant turn.',
    },
    {
      key: 'scrape.delay_seconds',
      effective_value: 1.5,
      env_value: 1.5,
      overridden: false,
      description: 'Minimum delay between scrapes to the same site (seconds).',
    },
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

afterEach(cleanup)

describe('SettingsPage', () => {
  it('lists keys with override status', async () => {
    vi.mocked(fetchAdminSettings).mockResolvedValue(SETTINGS)
    renderPage()
    expect(await screen.findByText('llm_runtime.max_tool_iters')).toBeTruthy()
    expect(screen.getByText('override')).toBeTruthy()
    expect(vi.mocked(deleteAdminSetting)).not.toHaveBeenCalled()
  })

  it('opens a modal to edit and saves typed JSON', async () => {
    vi.mocked(fetchAdminSettings).mockResolvedValue(SETTINGS)
    vi.mocked(putAdminSetting).mockResolvedValue({
      key: 'llm_runtime.max_tool_iters',
      value: 9,
      updated_by: 'u1',
      updated_at: '2026-07-30T00:00:00Z',
    })
    renderPage()
    fireEvent.click((await screen.findAllByRole('button', { name: 'Edit' }))[0]!)
    expect(await screen.findByRole('heading', { name: 'Edit setting' })).toBeTruthy()
    fireEvent.change(screen.getByLabelText('Value for llm_runtime.max_tool_iters'), {
      target: { value: '9' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Save' }))
    await waitFor(() =>
      expect(putAdminSetting).toHaveBeenCalledWith('llm_runtime.max_tool_iters', 9),
    )
  })

  it('shows the API detail in the modal when the save is rejected', async () => {
    vi.mocked(fetchAdminSettings).mockResolvedValue(SETTINGS)
    vi.mocked(putAdminSetting).mockRejectedValue(new ApiError(422, 'value must be >= 1'))
    renderPage()
    fireEvent.click((await screen.findAllByRole('button', { name: 'Edit' }))[0]!)
    fireEvent.click(await screen.findByRole('button', { name: 'Save' }))
    expect(await screen.findByText('value must be >= 1')).toBeTruthy()
  })
})
