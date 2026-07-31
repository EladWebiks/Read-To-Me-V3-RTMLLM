import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { UsersPage } from './UsersPage'
import { fetchMembershipPolicies } from '@/features/admin/api/membershipPolicies'
import { fetchAdminUsers, patchAdminUser } from '@/features/admin/api/users'

vi.mock('@/features/admin/api/users', () => ({
  fetchAdminUsers: vi.fn(),
  patchAdminUser: vi.fn(),
  softDeleteAdminUser: vi.fn(),
  restoreAdminUser: vi.fn(),
}))

vi.mock('@/features/admin/api/membershipPolicies', () => ({
  fetchMembershipPolicies: vi.fn(),
  patchMembershipPolicy: vi.fn(),
}))

const USER = {
  id: 'u1',
  username: 'reader',
  email: 'reader@example.com',
  is_admin: false,
  membership: 'free',
  google_linked: false,
  created_at: '2026-07-01T00:00:00Z',
  deleted_at: null,
}

function renderPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={queryClient}>
      <UsersPage />
    </QueryClientProvider>,
  )
}

// vitest runs with globals:false, so testing-library's auto-cleanup is not registered.
afterEach(cleanup)

describe('UsersPage', () => {
  it('renders one membership option per served policy', async () => {
    vi.mocked(fetchAdminUsers).mockResolvedValue({
      items: [USER],
      total: 1,
      limit: 50,
      offset: 0,
    })
    vi.mocked(fetchMembershipPolicies).mockResolvedValue({
      policies: [
        { membership: 'free', updated_at: '' },
        { membership: 'plus', updated_at: '' },
      ] as never,
      inherited: {},
    })
    renderPage()

    const select = await screen.findByLabelText(/Membership for reader/)
    await waitFor(() => {
      expect(screen.getAllByRole('option').map((o) => o.textContent)).toEqual([
        'free',
        'plus',
      ])
    })

    fireEvent.change(select, { target: { value: 'plus' } })
    await waitFor(() => {
      expect(vi.mocked(patchAdminUser)).toHaveBeenCalledWith('u1', { membership: 'plus' })
    })
  })
})
