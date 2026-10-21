import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import '@/shared/i18n'
import { ExternalLinkSafetyModal } from './ExternalLinkSafetyModal'

afterEach(cleanup)

describe('ExternalLinkSafetyModal', () => {
  it('closes after copy and after visit', async () => {
    const onClose = vi.fn()
    const onConfirm = vi.fn()
    const writeText = vi.fn().mockResolvedValue(undefined)
    Object.assign(navigator, { clipboard: { writeText } })
    const { rerender } = render(
      <ExternalLinkSafetyModal
        isOpen
        url="https://ranobes.top/novels/1.html"
        uiLang="en"
        onClose={onClose}
        onConfirm={onConfirm}
      />,
    )
    expect(screen.getByRole('dialog')).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: 'Copy address' }))
    await Promise.resolve()
    expect(writeText).toHaveBeenCalledWith('https://ranobes.top/novels/1.html')
    expect(onClose).toHaveBeenCalledTimes(1)
    onClose.mockClear()
    rerender(
      <ExternalLinkSafetyModal
        isOpen
        url="https://ranobes.top/novels/1.html"
        uiLang="he"
        onClose={onClose}
        onConfirm={onConfirm}
      />,
    )
    fireEvent.click(screen.getByRole('button', { name: 'מעבר לאתר' }))
    expect(onConfirm).toHaveBeenCalledTimes(1)
    expect(onClose).toHaveBeenCalledTimes(1)
  })
})
