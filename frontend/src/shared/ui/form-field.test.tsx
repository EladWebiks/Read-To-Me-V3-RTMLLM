import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'
import { FormError } from './form-error'
import { Input } from './input'

// vitest runs with globals:false, so testing-library's auto-cleanup is not registered.
afterEach(cleanup)

describe('FormError', () => {
  it('renders nothing for null, undefined and empty string', () => {
    expect(render(<FormError error={null} />).container.innerHTML).toBe('')
    expect(render(<FormError />).container.innerHTML).toBe('')
    expect(render(<FormError error="" />).container.innerHTML).toBe('')
  })

  it('renders a string error as an alert paragraph', () => {
    render(<FormError error="Nope." />)
    const alert = screen.getByRole('alert')
    expect(alert.textContent).toBe('Nope.')
    expect(alert.tagName).toBe('P')
    expect(alert.className).toContain('text-destructive')
  })

  it('unwraps an Error to its message', () => {
    render(<FormError error={new Error('Server said no')} />)
    expect(screen.getByRole('alert').textContent).toBe('Server said no')
  })

  it('renders a span when inline (for phrasing-content containers)', () => {
    render(<FormError inline error="Nope." />)
    expect(screen.getByRole('alert').tagName).toBe('SPAN')
  })

  it('takes an id so fields can reference it', () => {
    render(<FormError id="f-error" error="Bad" />)
    expect(screen.getByRole('alert').id).toBe('f-error')
  })
})

describe('Input size', () => {
  it('defaults to the standard h-9 style', () => {
    render(<Input aria-label="standard" readOnly value="" />)
    expect(screen.getByLabelText('standard').className).toContain('h-9')
  })

  it('sm renders the compact inline style', () => {
    render(<Input size="sm" aria-label="compact" readOnly value="" />)
    const className = screen.getByLabelText('compact').className
    expect(className).toContain('h-7')
    expect(className).toContain('text-xs')
    expect(className).not.toContain('w-full') // inline editors size themselves
  })
})
