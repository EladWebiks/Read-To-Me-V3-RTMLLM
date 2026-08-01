import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { PoliciesPage } from './PoliciesPage'
import {
  fetchMembershipPolicies,
  patchMembershipPolicy,
} from '@/features/admin/api/membershipPolicies'
import {
  createMembership,
  deactivateMembership,
  fetchMemberships,
  type AdminMembership,
} from '@/features/admin/api/memberships'

vi.mock('@/features/admin/api/membershipPolicies', async (importOriginal) => ({
  ...(await importOriginal<object>()),
  fetchMembershipPolicies: vi.fn(),
  patchMembershipPolicy: vi.fn(),
}))

vi.mock('@/features/admin/api/memberships', () => ({
  fetchMemberships: vi.fn(),
  createMembership: vi.fn(),
  patchMembership: vi.fn(),
  deactivateMembership: vi.fn(),
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

const FREE_TIER: AdminMembership = {
  slug: 'free',
  label: 'Free',
  description: null,
  price_label: null,
  rank: 0,
  is_active: true,
  is_default: true,
  user_count: 10,
  updated_at: '2026-07-31T00:00:00Z',
}

const PREMIUM_TIER: AdminMembership = {
  slug: 'premium',
  label: 'Premium',
  description: 'Premium tier',
  price_label: '$9/mo',
  rank: 1,
  is_active: true,
  is_default: false,
  user_count: 4,
  updated_at: '2026-07-31T00:00:00Z',
}

const LEGACY_TIER: AdminMembership = {
  slug: 'legacy',
  label: 'Legacy',
  description: null,
  price_label: null,
  rank: 2,
  is_active: false,
  is_default: false,
  user_count: 2,
  updated_at: '2026-07-31T00:00:00Z',
}

function mockData(tiers: AdminMembership[], policies: (typeof FREE)[] = [FREE]) {
  vi.mocked(fetchMemberships).mockResolvedValue({ memberships: tiers })
  vi.mocked(fetchMembershipPolicies).mockResolvedValue({
    policies,
    inherited: { max_tool_iters: 6 },
  })
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

afterEach(cleanup)

describe('PoliciesPage', () => {
  it('saves only changed fields, blank as null (inherit)', async () => {
    mockData([FREE_TIER])
    vi.mocked(patchMembershipPolicy).mockResolvedValue({ ...FREE, max_tool_iters: 3 })
    renderPage()
    const input = await screen.findByPlaceholderText('inherit (6)')
    fireEvent.change(input, { target: { value: '3' } })
    const hitlInput = screen.getByDisplayValue('2')
    fireEvent.change(hitlInput, { target: { value: '' } })
    fireEvent.click(screen.getByRole('button', { name: 'Save' }))
    await screen.findByRole('button', { name: 'Save' })
    expect(vi.mocked(patchMembershipPolicy)).toHaveBeenCalledWith('free', {
      max_tool_iters: 3,
      max_hitl_rounds: null,
    })
  })

  it('renders one card per tier in rank order, using the tier label as heading', async () => {
    mockData([FREE_TIER, PREMIUM_TIER, LEGACY_TIER], [FREE])
    renderPage()
    await screen.findByRole('heading', { name: 'Free' })
    const headings = screen.getAllByRole('heading', { level: 2 })
    expect(headings.map((h) => h.textContent)).toEqual(['Free', 'Premium', 'Legacy'])
  })

  it('renders a blank card for a tier with no matching policy row', async () => {
    mockData([FREE_TIER, LEGACY_TIER], [FREE])
    renderPage()
    const heading = await screen.findByText('Legacy')
    const card = heading.closest('.rounded-lg')
    expect(card).toBeTruthy()
    const inputs = within(card as HTMLElement).getAllByPlaceholderText(/inherit/)
    expect(inputs.every((el) => (el as HTMLInputElement).value === '')).toBe(true)
  })

  it('dims inactive tiers, showing Reactivate but not Deactivate', async () => {
    mockData([FREE_TIER, LEGACY_TIER], [FREE])
    renderPage()
    const heading = await screen.findByText('Legacy')
    const wrapper = heading.closest('.opacity-60')
    expect(wrapper).toBeTruthy()
    const scoped = within(wrapper as HTMLElement)
    expect(scoped.getByRole('button', { name: 'Reactivate' })).toBeTruthy()
    expect(scoped.queryByRole('button', { name: 'Deactivate' })).toBeNull()
    // Regression: an inactive, non-default tier must not offer "Make
    // default" — crowning it would leave is_active=false, is_default=true.
    expect(scoped.queryByRole('button', { name: 'Make default' })).toBeNull()
  })

  it('opens the create dialog from New tier and submits a create request', async () => {
    mockData([FREE_TIER])
    vi.mocked(createMembership).mockResolvedValue({ ...FREE_TIER, slug: 'gold' })
    renderPage()
    await screen.findByText('Free')
    fireEvent.click(screen.getByRole('button', { name: 'New tier' }))

    fireEvent.change(await screen.findByLabelText('Slug'), { target: { value: 'gold' } })
    fireEvent.change(screen.getByLabelText('Label'), { target: { value: 'Gold' } })
    fireEvent.change(screen.getByLabelText('Rank'), { target: { value: '3' } })
    fireEvent.change(screen.getByLabelText('Description'), {
      target: { value: 'Great tier' },
    })
    fireEvent.change(screen.getByLabelText('Price label'), { target: { value: '$5' } })
    fireEvent.click(screen.getByRole('button', { name: 'Save' }))

    await screen.findByText('Free')
    expect(vi.mocked(createMembership)).toHaveBeenCalledWith({
      slug: 'gold',
      label: 'Gold',
      rank: 3,
      description: 'Great tier',
      price_label: '$5',
    })
  })

  it('deactivates a tier, migrating its users to the chosen target', async () => {
    mockData([FREE_TIER, PREMIUM_TIER], [FREE])
    vi.mocked(deactivateMembership).mockResolvedValue({
      ...PREMIUM_TIER,
      is_active: false,
    })
    const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(true)
    renderPage()
    await screen.findByText('Premium')

    const select = screen.getByLabelText('Migrate Premium users to')
    expect(within(select).queryByText('Premium')).toBeNull()
    expect(within(select).getByText('Free')).toBeTruthy()

    fireEvent.click(screen.getByRole('button', { name: 'Deactivate' }))

    expect(confirmSpy).toHaveBeenCalledWith(
      'Deactivate Premium? 4 user(s) will move to free.',
    )
    await waitFor(() =>
      expect(vi.mocked(deactivateMembership)).toHaveBeenCalledWith('premium', 'free'),
    )
    confirmSpy.mockRestore()
  })
})
