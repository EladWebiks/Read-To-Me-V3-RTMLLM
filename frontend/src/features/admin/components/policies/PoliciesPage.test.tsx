import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { PoliciesPage } from './PoliciesPage'
import {
  fetchMembershipPolicies,
  patchMembershipPolicy,
} from '@/features/admin/api/membershipPolicies'

vi.mock('@/features/admin/api/membershipPolicies', async (importOriginal) => ({
  ...(await importOriginal<object>()),
  fetchMembershipPolicies: vi.fn(),
  patchMembershipPolicy: vi.fn(),
}))

const FREE = {
  membership: 'free',
  max_tool_iters: null,
  max_external_calls: null,
  max_turn_tokens_in: null,
  max_turn_tokens_out: null,
  max_turn_cost_usd: null,
  run_deadline_seconds: null,
  max_hitl_rounds: 2,
  updated_at: '2026-07-31T00:00:00Z',
}

function renderPage() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  return render(
    <QueryClientProvider client={queryClient}>
      <PoliciesPage />
    </QueryClientProvider>,
  )
}

describe('PoliciesPage', () => {
  it('renders inherit placeholders for NULL caps', async () => {
    vi.mocked(fetchMembershipPolicies).mockResolvedValue({
      policies: [FREE],
      inherited: { max_tool_iters: 6 },
    })
    renderPage()
    expect(await screen.findByText('free')).toBeTruthy()
    expect(screen.getByPlaceholderText('inherit (6)')).toBeTruthy()
  })

  it('saves only changed fields, blank as null (inherit)', async () => {
    vi.mocked(fetchMembershipPolicies).mockResolvedValue({
      policies: [FREE],
      inherited: { max_tool_iters: 6 },
    })
    vi.mocked(patchMembershipPolicy).mockResolvedValue({
      ...FREE,
      max_tool_iters: 3,
    })
    renderPage()
    const input = await screen.findByPlaceholderText('inherit (6)')
    fireEvent.change(input, { target: { value: '3' } })
    const hitlInput = screen.getByDisplayValue('2')
    fireEvent.change(hitlInput, { target: { value: '' } })
    fireEvent.click(screen.getByRole('button', { name: 'Save' }))
    await waitFor(() =>
      expect(vi.mocked(patchMembershipPolicy)).toHaveBeenCalledWith('free', {
        max_tool_iters: 3,
        max_hitl_rounds: null,
      }),
    )
  })
})
