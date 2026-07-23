import { describe, expect, it } from 'vitest'
import { clampPosition, defaultFloatingPosition } from './assistantGeometry'

describe('assistantGeometry', () => {
  it('defaults to the bottom-right margin', () => {
    // jsdom window is typically 1024x768
    const pos = defaultFloatingPosition(400, 500)
    expect(pos.x).toBeGreaterThan(0)
    expect(pos.y).toBeGreaterThan(0)
    expect(pos.x + 400).toBeLessThanOrEqual(window.innerWidth)
    expect(pos.y + 500).toBeLessThanOrEqual(window.innerHeight)
  })

  it('clamps into the viewport', () => {
    const pos = clampPosition(-40, 9999, 200, 200)
    expect(pos.x).toBe(8)
    expect(pos.y).toBeLessThanOrEqual(window.innerHeight - 200 - 8)
  })
})
