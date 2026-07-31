import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router'
import { afterEach, describe, expect, it } from 'vitest'
import type { User } from '@/features/auth/types'
import { TooltipProvider } from '@/shared/ui'
import { UserAvatar } from './UserAvatar'

const user: User = {
  id: 'u-1',
  username: 'idan',
  email: 'idan.avin@gmail.com',
  picture_url: 'https://lh3.example.com/photo.jpg',
  is_admin: true,
  membership: 'free',
  created_at: '2026-07-30T00:00:00Z',
}

/** The avatar is a dropdown trigger, so it needs router context to navigate. */
function renderAvatar(overrides: Partial<User> = {}) {
  return render(
    <TooltipProvider>
      <MemoryRouter initialEntries={['/library']}>
        <Routes>
          <Route
            path="/library"
            element={<UserAvatar user={{ ...user, ...overrides }} />}
          />
          <Route path="/usage" element={<div>usage-page-marker</div>} />
        </Routes>
      </MemoryRouter>
    </TooltipProvider>,
  )
}

describe('UserAvatar', () => {
  afterEach(cleanup)

  it('renders the profile image when picture_url is set', () => {
    const { container } = renderAvatar()
    const img = container.querySelector('img')
    expect(img?.getAttribute('src')).toBe('https://lh3.example.com/photo.jpg')
    expect(img?.getAttribute('referrerpolicy')).toBe('no-referrer')
  })

  it('renders the initial-letter fallback without a picture', () => {
    const { container } = renderAvatar({ picture_url: null })
    expect(container.querySelector('img')).toBeNull()
    expect(container.textContent).toContain('i')
  })

  it('falls back to the initial letter when the image fails to load', () => {
    const { container } = renderAvatar()
    const img = container.querySelector('img')
    expect(img).not.toBeNull()
    fireEvent.error(img as HTMLImageElement)
    expect(container.querySelector('img')).toBeNull()
    expect(container.textContent).toContain('i')
  })

  it('opens a menu with the email, tier, and a Plan & usage link', async () => {
    renderAvatar()
    fireEvent.keyDown(screen.getByLabelText('Account menu'), { key: 'Enter' })
    expect(await screen.findByText('idan.avin@gmail.com')).toBeTruthy()
    expect(screen.getByText('free plan')).toBeTruthy()

    fireEvent.click(screen.getByText('Plan & usage'))
    expect(await screen.findByText('usage-page-marker')).toBeTruthy()
  })
})
