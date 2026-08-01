import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'
import { FormError } from './form-error'
import { FormField } from './form-field'
import { Input } from './input'
import { Select } from './select'
import { SelectField } from './select-field'
import { TextField } from './text-field'

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

describe('TextField', () => {
  it('associates the label with the input', () => {
    render(<TextField id="f" label="AI tokens" readOnly value="" />)
    expect(screen.getByLabelText('AI tokens').tagName).toBe('INPUT')
  })

  it('wires an error to aria-invalid, aria-describedby and an alert', () => {
    render(<TextField id="f" label="L" error="Bad" readOnly value="" />)
    const input = screen.getByLabelText('L')
    expect(input.getAttribute('aria-invalid')).toBe('true')
    expect(input.getAttribute('aria-describedby')).toBe('f-error')
    expect(screen.getByRole('alert').id).toBe('f-error')
  })

  it('accepts an Error object as the error', () => {
    render(<TextField id="f" label="L" error={new Error('boom')} readOnly value="" />)
    expect(screen.getByRole('alert').textContent).toBe('boom')
  })

  it('lists hint and error ids in aria-describedby, hint first', () => {
    render(<TextField id="f" label="L" hint="H" error="E" readOnly value="" />)
    const input = screen.getByLabelText('L')
    expect(input.getAttribute('aria-describedby')).toBe('f-hint f-error')
    expect(document.getElementById('f-hint')?.textContent).toBe('H')
  })

  it('adds no aria noise when healthy', () => {
    render(<TextField id="f" label="L" readOnly value="" />)
    const input = screen.getByLabelText('L')
    expect(input.getAttribute('aria-invalid')).toBeNull()
    expect(input.getAttribute('aria-describedby')).toBeNull()
    expect(screen.queryByRole('alert')).toBeNull()
  })

  it('numeric sets decimal inputMode and tabular numerals', () => {
    render(<TextField id="f" label="L" numeric readOnly value="" />)
    const input = screen.getByLabelText('L')
    expect(input.getAttribute('inputmode')).toBe('decimal')
    expect(input.className).toContain('tabular-nums')
  })

  it('forwards native input props', () => {
    render(
      <TextField
        id="f"
        label="L"
        type="number"
        min={1}
        placeholder="p"
        readOnly
        value=""
      />,
    )
    const input = screen.getByLabelText('L')
    expect(input.getAttribute('type')).toBe('number')
    expect(input.getAttribute('min')).toBe('1')
    expect(input.getAttribute('placeholder')).toBe('p')
  })
})

describe('FormField', () => {
  it('labels a caller-rendered control and exposes hint/error ids', () => {
    render(
      <FormField id="d" label="Description" hint="Optional" error="Too long">
        <textarea id="d" aria-describedby="d-hint d-error" />
      </FormField>,
    )
    expect(screen.getByLabelText('Description').tagName).toBe('TEXTAREA')
    expect(document.getElementById('d-hint')?.textContent).toBe('Optional')
    expect(document.getElementById('d-error')?.textContent).toBe('Too long')
    expect(screen.getByRole('alert').id).toBe('d-error')
  })

  it('renders no hint or error nodes when it has none', () => {
    render(
      <FormField id="d" label="Description">
        <textarea id="d" />
      </FormField>,
    )
    expect(document.getElementById('d-hint')).toBeNull()
    expect(screen.queryByRole('alert')).toBeNull()
  })
})

describe('Select size', () => {
  it('defaults to the standard h-9 style', () => {
    render(
      <Select aria-label="standard" value="a" onChange={() => {}}>
        <option value="a">A</option>
      </Select>,
    )
    const select = screen.getByLabelText('standard')
    expect(select.tagName).toBe('SELECT')
    expect(select.className).toContain('h-9')
    expect(select.className).toContain('w-full')
  })

  it('sm renders the compact inline style', () => {
    render(
      <Select size="sm" aria-label="compact" value="a" onChange={() => {}}>
        <option value="a">A</option>
      </Select>,
    )
    const className = screen.getByLabelText('compact').className
    expect(className).toContain('h-7')
    expect(className).toContain('text-xs')
    expect(className).not.toContain('w-full') // inline editors size themselves
  })

  it('forwards native select props', () => {
    render(
      <Select
        aria-label="native"
        name="tier"
        disabled
        required
        value="a"
        onChange={() => {}}
      >
        <option value="a">A</option>
      </Select>,
    )
    const select = screen.getByLabelText('native')
    expect(select.getAttribute('name')).toBe('tier')
    expect(select.hasAttribute('disabled')).toBe(true)
    expect(select.hasAttribute('required')).toBe(true)
  })
})

describe('SelectField', () => {
  const options = (
    <>
      <option value="">Default</option>
      <option value="edge">Edge</option>
      <option value="sapi">SAPI</option>
    </>
  )

  it('associates the label with the select', () => {
    render(
      <SelectField id="v" label="Voice" value="edge" onChange={() => {}}>
        {options}
      </SelectField>,
    )
    expect(screen.getByLabelText('Voice').tagName).toBe('SELECT')
  })

  it('renders options and selects the current value', () => {
    render(
      <SelectField id="v" label="Voice" value="sapi" onChange={() => {}}>
        {options}
      </SelectField>,
    )
    const select = screen.getByLabelText('Voice') as HTMLSelectElement
    expect(screen.getAllByRole('option')).toHaveLength(3)
    expect(select.value).toBe('sapi')
  })

  it('wires an error to aria-invalid, aria-describedby and an alert', () => {
    render(
      <SelectField id="v" label="Voice" error="Bad" value="" onChange={() => {}}>
        {options}
      </SelectField>,
    )
    const select = screen.getByLabelText('Voice')
    expect(select.getAttribute('aria-invalid')).toBe('true')
    expect(select.getAttribute('aria-describedby')).toBe('v-error')
    expect(screen.getByRole('alert').id).toBe('v-error')
  })

  it('lists hint and error ids in aria-describedby, hint first', () => {
    render(
      <SelectField id="v" label="Voice" hint="H" error="E" value="" onChange={() => {}}>
        {options}
      </SelectField>,
    )
    expect(screen.getByLabelText('Voice').getAttribute('aria-describedby')).toBe(
      'v-hint v-error',
    )
    expect(document.getElementById('v-hint')?.textContent).toBe('H')
  })

  it('adds no aria noise when healthy', () => {
    render(
      <SelectField id="v" label="Voice" value="" onChange={() => {}}>
        {options}
      </SelectField>,
    )
    const select = screen.getByLabelText('Voice')
    expect(select.getAttribute('aria-invalid')).toBeNull()
    expect(select.getAttribute('aria-describedby')).toBeNull()
    expect(screen.queryByRole('alert')).toBeNull()
  })

  it('forwards native select props', () => {
    render(
      <SelectField
        id="v"
        label="Voice"
        name="voice"
        disabled
        value=""
        onChange={() => {}}
      >
        {options}
      </SelectField>,
    )
    const select = screen.getByLabelText('Voice')
    expect(select.getAttribute('name')).toBe('voice')
    expect(select.hasAttribute('disabled')).toBe(true)
  })
})
