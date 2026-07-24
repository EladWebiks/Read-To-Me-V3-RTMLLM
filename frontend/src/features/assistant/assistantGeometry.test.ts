import { afterEach, describe, expect, it, vi } from 'vitest'
import {
  clampPosition,
  defaultFloatingPosition,
  panelSizeOrFallback,
  resolveFloatingPosition,
} from './assistantGeometry'

afterEach(() => {
  vi.unstubAllGlobals()
})

function stubViewport(width: number, height: number) {
  vi.stubGlobal('innerWidth', width)
  vi.stubGlobal('innerHeight', height)
  vi.stubGlobal(
    'matchMedia',
    vi.fn((query: string) => ({
      matches: query.includes('max-width: 639px') ? width <= 639 : false,
      media: query,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      addListener: vi.fn(),
      removeListener: vi.fn(),
      dispatchEvent: vi.fn(),
      onchange: null,
    })),
  )
}

describe('assistantGeometry', () => {
  it('defaults to the bottom-right margin on desktop', () => {
    stubViewport(1024, 768)
    const pos = defaultFloatingPosition(400, 500)
    expect(pos.x + 400).toBeLessThanOrEqual(1024)
    expect(pos.y + 500).toBeLessThanOrEqual(768)
    expect(pos.x).toBeGreaterThan(400)
  })

  it('centers on compact viewports', () => {
    stubViewport(390, 844)
    const pos = defaultFloatingPosition(374, 500)
    expect(pos.x).toBe(Math.round((390 - 374) / 2))
    expect(pos.y).toBe(Math.round((844 - 500) / 2))
  })

  it('clamps into the viewport', () => {
    stubViewport(1024, 768)
    const pos = clampPosition(-40, 9999, 200, 200)
    expect(pos.x).toBe(8)
    expect(pos.y).toBeLessThanOrEqual(768 - 200 - 8)
  })

  it('locks x to center when clamping on compact', () => {
    stubViewport(390, 844)
    const pos = clampPosition(200, 40, 374, 500)
    expect(pos.x).toBe(Math.round((390 - 374) / 2))
    expect(pos.y).toBe(40)
  })

  it('ignores desktop x when resolving on compact', () => {
    stubViewport(390, 844)
    const pos = resolveFloatingPosition({ x: 900, y: 120 }, 374, 500)
    expect(pos.x).toBe(Math.round((390 - 374) / 2))
    expect(pos.y).toBe(120)
  })

  it('falls back to viewport-safe panel size', () => {
    stubViewport(375, 667)
    const size = panelSizeOrFallback(0, 0)
    expect(size.width).toBeLessThanOrEqual(375)
    expect(size.height).toBeLessThanOrEqual(667)
  })
})
