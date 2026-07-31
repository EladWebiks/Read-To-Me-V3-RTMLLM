import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import type { PlansResponse } from '../api/plans'
import { plansKey } from '../hooks/usePlans'
import { PlansSection } from './PlansSection'

const { fetchPlans, switchPlan } = vi.hoisted(() => ({
  fetchPlans: vi.fn(),
  switchPlan: vi.fn(),
}))

vi.mock('../api/plans', () => ({ fetchPlans, switchPlan }))

const plans: PlansResponse = {
  plans: [
    { slug: 'free', label: 'Free', description: null, price_label: null, current: true },
    {
      slug: 'premium',
      label: 'Premium',
      description: 'More stuff',
      price_label: '$9/mo',
      current: false,
    },
  ],
  can_switch: true,
}

function newClient() {
  return new QueryClient({ defaultOptions: { queries: { retry: false } } })
}

function renderSection(client: QueryClient) {
  return render(
    <QueryClientProvider client={client}>
      <PlansSection />
    </QueryClientProvider>,
  )
}

afterEach(() => {
  vi.clearAllMocks()
})

describe('PlansSection', () => {
  it('renders both plan cards with a current marker and a switch button', async () => {
    fetchPlans.mockResolvedValue(plans)
    renderSection(newClient())

    expect(await screen.findByText('Free')).toBeTruthy()
    expect(screen.getByText('Current plan')).toBeTruthy()
    expect(screen.getByText('Premium')).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Switch to Premium' })).toBeTruthy()
  })

  it('clicking the switch button confirms and calls switchPlan with the target slug', async () => {
    fetchPlans.mockResolvedValue(plans)
    switchPlan.mockResolvedValue({})
    const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(true)
    renderSection(newClient())

    const button = await screen.findByRole('button', { name: 'Switch to Premium' })
    fireEvent.click(button)

    expect(confirmSpy).toHaveBeenCalledWith('Switch to Premium?')
    await waitFor(() => expect(switchPlan).toHaveBeenCalledWith('premium'))
  })

  it('renders nothing when can_switch is false', async () => {
    fetchPlans.mockResolvedValue({ plans: plans.plans, can_switch: false })
    const client = newClient()
    const { container } = renderSection(client)

    await waitFor(() => expect(client.getQueryState(plansKey)?.status).toBe('success'))
    expect(container.firstChild).toBeNull()
  })

  it('renders nothing while loading', () => {
    fetchPlans.mockReturnValue(new Promise(() => {}))
    const { container } = renderSection(newClient())

    expect(container.firstChild).toBeNull()
  })
})
