import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import type { MeUsage } from '../api/meUsage'
import { UsagePage } from './UsagePage'

const usage: MeUsage = {
  membership: 'free',
  membership_label: 'Free Tier',
  exempt: false,
  as_of: '2026-07-31T12:00:00+00:00',
  resets_at: '2026-08-01T00:00:00+00:00',
  kinds: [
    {
      kind: 'llm_tokens',
      label: 'AI tokens',
      unit: 'tokens',
      window: 'month',
      used: 4500,
      limit: 5000,
    },
    {
      kind: 'llm_cost_usd',
      label: 'AI spend',
      unit: 'USD',
      window: 'month',
      used: 0.5,
      limit: null,
    },
    {
      kind: 'storage_bytes',
      label: 'Download storage',
      unit: 'bytes',
      window: 'standing',
      used: 52428800,
      limit: null,
    },
  ],
}

vi.mock('../api/meUsage', () => ({ fetchMeUsage: vi.fn(async () => usage) }))

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <UsagePage />
    </QueryClientProvider>,
  )
}

// This project wires no jest-dom setup file, so assertions use plain vitest
// matchers (`toBeTruthy` / `getAttribute`) like the rest of the suite.
describe('UsagePage', () => {
  it('renders tier, reset date, month meters, and the storage section', async () => {
    renderPage()
    expect(await screen.findByText('Free Tier')).toBeTruthy()
    expect(screen.getByText(/Usage resets August 1, 2026/)).toBeTruthy()
    expect(screen.getByText('AI tokens')).toBeTruthy()
    expect(screen.getByText('4,500 / 5,000')).toBeTruthy()
    expect(screen.getByText('$0.50 · Unlimited')).toBeTruthy() // llm_cost_usd, no bar
    expect(screen.getByText('50.0 MB · Unlimited')).toBeTruthy() // storage section
    expect(screen.getByText(/Frees up when downloads expire/)).toBeTruthy()
  })

  it('marks a ≥80% meter as warning and draws no bar for unlimited kinds', async () => {
    renderPage()
    const meter = await screen.findByRole('progressbar', { name: 'AI tokens' })
    expect(meter.getAttribute('data-state')).toBe('warn') // 4500/5000 = 90%
    expect(screen.getAllByRole('progressbar')).toHaveLength(1) // only the limited kind
  })
})
