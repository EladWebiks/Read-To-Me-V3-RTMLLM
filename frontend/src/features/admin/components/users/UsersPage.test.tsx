import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { UsersPage } from './UsersPage'
import { fetchMemberships } from '@/features/admin/api/memberships'
import { fetchAdminUsers, patchAdminUser } from '@/features/admin/api/users'

vi.mock('@/features/admin/api/users', () => ({
  fetchAdminUsers: vi.fn(),
  patchAdminUser: vi.fn(),
  softDeleteAdminUser: vi.fn(),
  restoreAdminUser: vi.fn(),
}))

vi.mock('@/features/admin/api/memberships', () => ({
  fetchMemberships: vi.fn(),
  createMembership: vi.fn(),
  patchMembership: vi.fn(),
  deactivateMembership: vi.fn(),
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
  it('renders one membership option per active tier, in rank order', async () => {
    vi.mocked(fetchAdminUsers).mockResolvedValue({
      items: [USER],
      total: 1,
      limit: 50,
      offset: 0,
    })
    vi.mocked(fetchMemberships).mockResolvedValue({
      memberships: [
        { slug: 'free', is_active: true, rank: 0 },
        { slug: 'premium', is_active: true, rank: 1 },
        { slug: 'legacy', is_active: false, rank: 2 },
      ] as never,
    })
    renderPage()

    const select = await screen.findByLabelText(/Membership for reader/)
    await waitFor(() => {
      expect(screen.getAllByRole('option').map((o) => o.textContent)).toEqual([
        'free',
        'premium',
      ])
    })

    fireEvent.change(select, { target: { value: 'premium' } })
    await waitFor(() => {
      expect(vi.mocked(patchAdminUser)).toHaveBeenCalledWith('u1', {
        membership: 'premium',
      })
    })
  })
})
