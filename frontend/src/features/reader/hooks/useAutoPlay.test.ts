import { renderHook } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { useAutoPlay } from './useAutoPlay'
import type { ReaderCursor } from '@/features/reader/types'

type Props = { key: string | null; count: number; from: ReaderCursor }

function render(play: (from: ReaderCursor) => void, initial: Props) {
  return renderHook(
    (props: Props) => useAutoPlay(props.key, props.count, props.from, play),
    {
      initialProps: initial,
    },
  )
}

describe('useAutoPlay', () => {
  it('plays once and ignores cursor updates from saved progress', () => {
    const play = vi.fn()
    const view = render(play, {
      key: 'req-1',
      count: 3,
      from: { paragraphIndex: 0, wordIndex: 0 },
    })

    view.rerender({ key: 'req-1', count: 3, from: { paragraphIndex: 1, wordIndex: 4 } })
    view.rerender({ key: 'req-1', count: 3, from: { paragraphIndex: 2, wordIndex: 0 } })

    expect(play).toHaveBeenCalledTimes(1)
    expect(play).toHaveBeenCalledWith({ paragraphIndex: 0, wordIndex: 0 })
  })

  it('waits for content and uses the cursor known when it starts', () => {
    const play = vi.fn()
    const view = render(play, {
      key: 'req-1',
      count: 0,
      from: { paragraphIndex: 0, wordIndex: 0 },
    })

    view.rerender({ key: 'req-1', count: 5, from: { paragraphIndex: 7, wordIndex: 2 } })

    expect(play).toHaveBeenCalledTimes(1)
    expect(play).toHaveBeenCalledWith({ paragraphIndex: 7, wordIndex: 2 })
  })

  it('plays again for a new request and never without one', () => {
    const play = vi.fn()
    const view = render(play, {
      key: null,
      count: 3,
      from: { paragraphIndex: 0, wordIndex: 0 },
    })
    expect(play).not.toHaveBeenCalled()

    view.rerender({ key: 'req-1', count: 3, from: { paragraphIndex: 0, wordIndex: 0 } })
    view.rerender({ key: 'req-2', count: 3, from: { paragraphIndex: 4, wordIndex: 1 } })

    expect(play).toHaveBeenCalledTimes(2)
    expect(play).toHaveBeenLastCalledWith({ paragraphIndex: 4, wordIndex: 1 })
  })
})
