import { cleanup, fireEvent, render } from '@testing-library/react'
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

function renderAvatar(overrides: Partial<User> = {}) {
  return render(
    <TooltipProvider>
      <UserAvatar user={{ ...user, ...overrides }} />
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
})
