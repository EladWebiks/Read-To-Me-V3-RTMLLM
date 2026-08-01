import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { RequireAdmin } from './RequireAdmin'
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

function renderGuard() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={['/admin']}>
        <Routes>
          <Route path="/" element={<p>home</p>} />
          <Route element={<RequireAdmin />}>
            <Route path="/admin" element={<p>admin area</p>} />
          </Route>
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('RequireAdmin', () => {
  afterEach(cleanup)

  it('renders admin content for admins', async () => {
    vi.mocked(fetchMe).mockResolvedValue(me(true))
    renderGuard()
    expect(await screen.findByText('admin area')).toBeTruthy()
  })

  it('redirects non-admins home', async () => {
    vi.mocked(fetchMe).mockResolvedValue(me(false))
    renderGuard()
    expect(await screen.findByText('home')).toBeTruthy()
    expect(screen.queryByText('admin area')).toBeNull()
  })
})
