import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'
import { Skeleton, SkeletonText } from './skeleton'
import { InlineLoader, Spinner } from './spinner'

// vitest runs with globals:false, so testing-library's auto-cleanup is not registered.
afterEach(cleanup)

describe('Skeleton', () => {
  it('merges className onto the rtm-skeleton base', () => {
    const { container } = render(<Skeleton className="h-4 w-32" />)
    const block = container.firstElementChild as HTMLElement
    expect(block.className).toContain('rtm-skeleton')
    expect(block.className).toContain('h-4')
    expect(block.className).toContain('w-32')
  })

  it('is aria-hidden so it never reaches the accessibility tree', () => {
    const { container } = render(<Skeleton className="h-4" />)
    expect(container.firstElementChild?.getAttribute('aria-hidden')).toBe('true')
  })
})

describe('SkeletonText', () => {
  it('renders the requested number of bars, last one narrower', () => {
    const { container } = render(<SkeletonText lines={3} />)
    const bars = container.querySelectorAll('.rtm-skeleton')
    expect(bars).toHaveLength(3)
    expect(bars[2].className).toContain('w-3/5')
    expect(bars[0].className).toContain('w-full')
  })

  it('is aria-hidden at the wrapper', () => {
    const { container } = render(<SkeletonText />)
    expect(container.firstElementChild?.getAttribute('aria-hidden')).toBe('true')
  })
})

describe('Spinner', () => {
  it('spins and stays out of the accessibility tree', () => {
    const { container } = render(<Spinner />)
    const icon = container.firstElementChild as HTMLElement
    expect(icon.getAttribute('aria-hidden')).toBe('true')
    expect(icon.getAttribute('class') ?? '').toContain('animate-spin')
  })

  it('sm renders the compact size', () => {
    const { container } = render(<Spinner size="sm" />)
    expect((container.firstElementChild as HTMLElement).getAttribute('class')).toContain(
      'size-3.5',
    )
  })
})

describe('InlineLoader', () => {
  it('renders its label as visible text next to a hidden spinner', () => {
    render(<InlineLoader label="Loading chapters…" />)
    expect(screen.getByText('Loading chapters…')).toBeTruthy()
  })
})
