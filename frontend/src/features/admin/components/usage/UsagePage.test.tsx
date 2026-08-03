import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeAll, describe, expect, it, vi } from 'vitest'
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

beforeAll(() => {
  class ResizeObserverStub {
    observe() {}
    unobserve() {}
    disconnect() {}
  }
  class MutationObserverStub {
    observe() {}
    disconnect() {}
    takeRecords() {
      return []
    }
  }
  vi.stubGlobal('ResizeObserver', ResizeObserverStub)
  vi.stubGlobal('MutationObserver', MutationObserverStub)
})

const BREAKDOWN = { tokens_in: 700, tokens_out: 70, total_cost: 1.75, execution_count: 3 }

function renderPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={queryClient}>
      <UsagePage />
    </QueryClientProvider>,
  )
}

afterEach(cleanup)

function mockStats() {
  vi.mocked(fetchUsageOverview).mockResolvedValue({
    ...BREAKDOWN,
    period_start: '2026-07-01T00:00:00Z',
    period_end: '2026-08-01T00:00:00Z',
    by_model: [{ ...BREAKDOWN, provider: 'gemini', model: 'm1' }],
    by_task: [{ ...BREAKDOWN, task: 'chat' }],
    rejections: 5,
    rejections_by_kind: { llm_tokens: 5 },
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
        month_audio_chapters: 0,
        month_scrape_chapters: 0,
        month_epub_imports: 0,
        period_rejections: 2,
      },
    ],
    total: 1,
    limit: 25,
    offset: 0,
  })
}

describe('UsagePage', () => {
  it('shows statistics by default', async () => {
    mockStats()
    vi.mocked(fetchExecutions).mockResolvedValue({
      items: [],
      total: 0,
      limit: 25,
      offset: 0,
    })
    renderPage()
    expect(await screen.findByText('bob')).toBeTruthy()
    expect(screen.getAllByText('Tokens in').length).toBeGreaterThan(0)
    expect(screen.queryByText('400/40')).toBeNull()
  })

  it('switches to recent executions with the shared table', async () => {
    mockStats()
    vi.mocked(fetchExecutions).mockResolvedValue({
      items: [
        {
          id: 'e1',
          user_id: 'u2',
          username: 'bob',
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
      limit: 12,
      offset: 0,
    })
    renderPage()
    fireEvent.click(await screen.findByRole('tab', { name: 'Recent executions' }))
    expect(await screen.findByLabelText('Filter by username')).toBeTruthy()
    expect(await screen.findByText('400/40')).toBeTruthy()
    expect(screen.getAllByText('bob').length).toBeGreaterThan(0)
    expect(screen.getAllByText('ok').length).toBeGreaterThan(0)
    expect(
      screen
        .getByRole('tab', { name: 'Recent executions' })
        .getAttribute('aria-selected'),
    ).toBe('true')
  })
})
