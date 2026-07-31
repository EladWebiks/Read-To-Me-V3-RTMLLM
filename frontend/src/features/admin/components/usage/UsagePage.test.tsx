import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { UsagePage } from './UsagePage'
import {
  fetchExecutions,
  fetchUsageByUser,
  fetchUsageOverview,
} from '@/features/admin/api/usage'

vi.mock('@/features/admin/api/usage', () => ({
  fetchUsageOverview: vi.fn(),
  fetchUsageByUser: vi.fn(),
  fetchExecutions: vi.fn(),
}))

const BREAKDOWN = { tokens_in: 700, tokens_out: 70, total_cost: 1.75, execution_count: 3 }

function renderPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={queryClient}>
      <UsagePage />
    </QueryClientProvider>,
  )
}

describe('UsagePage', () => {
  it('renders tiles, breakdowns, per-user rows, and executions', async () => {
    vi.mocked(fetchUsageOverview).mockResolvedValue({
      ...BREAKDOWN,
      period_start: '2026-07-01T00:00:00Z',
      period_end: '2026-08-01T00:00:00Z',
      by_model: [{ ...BREAKDOWN, provider: 'gemini', model: 'm1' }],
      by_task: [{ ...BREAKDOWN, task: 'chat' }],
    })
    vi.mocked(fetchUsageByUser).mockResolvedValue({
      items: [
        {
          ...BREAKDOWN,
          user_id: 'u2',
          username: 'bob',
          membership: 'free',
          month_tokens: 0,
          month_cost: 0,
          llm_tokens_limit: null,
          llm_cost_limit: null,
        },
      ],
      total: 1,
      limit: 25,
      offset: 0,
    })
    vi.mocked(fetchExecutions).mockResolvedValue({
      items: [
        {
          id: 'e1',
          user_id: 'u2',
          conversation_id: null,
          task: 'chat',
          provider: 'gemini',
          model: 'm1',
          tokens_in: 400,
          tokens_out: 40,
          cost: 1,
          latency_ms: 120,
          status: 'ok',
          fallback_used: false,
          created_at: '2026-07-30T12:00:00Z',
          error: null,
        },
      ],
      total: 1,
      limit: 25,
      offset: 0,
    })
    renderPage()
    // The same figures repeat across tiles, breakdowns and the per-user row,
    // so every shared value is matched with *All* queries.
    expect(await screen.findByText('Tokens in')).toBeTruthy()
    expect((await screen.findAllByText('700')).length).toBeGreaterThan(0)
    expect(screen.getAllByText('$1.7500').length).toBeGreaterThan(0)
    expect((await screen.findAllByText('gemini/m1')).length).toBeGreaterThan(0)
    expect(await screen.findByText('bob')).toBeTruthy()
    expect((await screen.findAllByText('ok')).length).toBeGreaterThan(0)
    expect(await screen.findByText('400/40')).toBeTruthy()
  })
})
