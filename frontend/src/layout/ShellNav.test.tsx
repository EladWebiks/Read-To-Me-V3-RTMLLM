import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { ShellNavLinks } from './ShellNav'
import { fetchMe } from '@/features/auth/api'
import type { MeResponse } from '@/features/auth/types'

vi.mock('@/features/auth/api', () => ({
  fetchMe: vi.fn(),
}))

function me(isAdmin: boolean): MeResponse {
  return {
    user: {
      id: 'u1',
      username: 'boss',
      email: null,
      picture_url: null,
      is_admin: isAdmin,
      membership: 'free',
      created_at: '2026-01-01T00:00:00Z',
    },
    membership_label: 'Free',
  }
}

function renderNav() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <ShellNavLinks readerActive={false} />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('ShellNavLinks admin gating', () => {
  afterEach(cleanup)

  it('shows the Admin link for admins', async () => {
    vi.mocked(fetchMe).mockResolvedValue(me(true))
    renderNav()
    expect(await screen.findByText('Admin')).toBeTruthy()
  })

  it('hides the Admin link for non-admins', async () => {
    vi.mocked(fetchMe).mockResolvedValue(me(false))
    renderNav()
    expect(await screen.findByText('Library')).toBeTruthy()
    expect(screen.queryByText('Admin')).toBeNull()
  })
})
