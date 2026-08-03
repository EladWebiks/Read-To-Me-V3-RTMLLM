import { act } from 'react'
import { renderHook } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { usePageState } from './usePageState'

describe('usePageState', () => {
  it('pages forward and back within bounds', () => {
    const { result } = renderHook(() => usePageState(10))
    expect(result.current.offset).toBe(0)
    act(() => result.current.next(25))
    expect(result.current.offset).toBe(10)
    act(() => result.current.next(25))
    expect(result.current.offset).toBe(20)
    act(() => result.current.next(25))
    expect(result.current.offset).toBe(20)
    act(() => result.current.prev())
    expect(result.current.offset).toBe(10)
    act(() => result.current.reset())
    expect(result.current.offset).toBe(0)
  })

  it('never goes below zero', () => {
    const { result } = renderHook(() => usePageState(10))
    act(() => result.current.prev())
    expect(result.current.offset).toBe(0)
  })

  it('realigns offset when limit changes', () => {
    const { result, rerender } = renderHook(({ limit }) => usePageState(limit), {
      initialProps: { limit: 10 },
    })
    act(() => result.current.next(100))
    expect(result.current.offset).toBe(10)
    rerender({ limit: 15 })
    expect(result.current.offset).toBe(0)
  })

  it('jumps to a page via setPage', () => {
    const { result } = renderHook(() => usePageState(10))
    act(() => result.current.setPage(3))
    expect(result.current.offset).toBe(20)
    expect(result.current.page).toBe(3)
  })
})
