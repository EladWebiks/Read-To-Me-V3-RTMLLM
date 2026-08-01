import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import type { AdminMembership } from '@/features/admin/api/memberships'
import { TierDeactivate } from './TierDeactivate'
import { deactivateMembership } from '@/features/admin/api/memberships'

vi.mock('@/features/admin/api/memberships', () => ({
  fetchMemberships: vi.fn(),
  createMembership: vi.fn(),
  patchMembership: vi.fn(),
  deactivateMembership: vi.fn(),
}))

function tierFrom(
  slug: string,
  overrides: Partial<AdminMembership> = {},
): AdminMembership {
  return {
    slug,
    label: slug,
    description: null,
    price_label: null,
    rank: 0,
    is_active: true,
    is_default: false,
    user_count: 0,
    updated_at: '2026-07-31T00:00:00Z',
    ...overrides,
  }
}

const PREMIUM = tierFrom('premium', { label: 'Premium' })
const GOLD = tierFrom('gold', { label: 'Gold' })
const FREE = tierFrom('free', { label: 'Free', is_default: true })

function renderDeactivate(allTiers: AdminMembership[], client: QueryClient) {
  return render(
    <QueryClientProvider client={client}>
      <TierDeactivate tier={PREMIUM} allTiers={allTiers} />
    </QueryClientProvider>,
  )
}

afterEach(cleanup)

describe('TierDeactivate', () => {
  it('falls back to the first remaining tier when the selected target disappears from a refetch', async () => {
    // Simulates a sibling deactivation shrinking `allTiers` mid-session: the
    // fix derives the select's value during render instead of syncing state
    // via an effect, so a stale `target` can never render blank or get
    // submitted once its slug drops out of `others`.
    const client = new QueryClient()
    const { rerender } = renderDeactivate([PREMIUM, GOLD, FREE], client)

    const select = screen.getByLabelText('Migrate Premium users to') as HTMLSelectElement
    fireEvent.change(select, { target: { value: 'gold' } })
    expect(select.value).toBe('gold')

    // Gold gets deactivated elsewhere and drops out of the candidate list.
    rerender(
      <QueryClientProvider client={client}>
        <TierDeactivate tier={PREMIUM} allTiers={[PREMIUM, FREE]} />
      </QueryClientProvider>,
    )

    expect(select.value).toBe('free')

    const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(true)
    fireEvent.click(screen.getByRole('button', { name: 'Deactivate' }))
    await waitFor(() =>
      expect(vi.mocked(deactivateMembership)).toHaveBeenCalledWith('premium', 'free'),
    )
    confirmSpy.mockRestore()
  })
})
