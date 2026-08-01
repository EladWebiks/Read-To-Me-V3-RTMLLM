import type { ReactNode, SelectHTMLAttributes } from 'react'
import { describedBy } from './field-aria'
import { FormField } from './form-field'
import { Select } from './select'

type Props = Omit<SelectHTMLAttributes<HTMLSelectElement>, 'id' | 'size'> & {
  id: string
  label: ReactNode
  hint?: ReactNode
  error?: string | Error | null
  /** <option> elements — call sites disagree on option shape, so no mapping prop. */
  children: ReactNode
}

/** Label + Select + hint + error as one unit, with the ARIA wiring done. */
export function SelectField({ id, label, hint, error, children, ...props }: Props) {
  const hasError = error != null && error !== ''
  return (
    <FormField id={id} label={label} hint={hint} error={error}>
      <Select
        {...props}
        id={id}
        aria-invalid={hasError ? true : undefined}
        aria-describedby={describedBy(id, hint != null, hasError)}
      >
        {children}
      </Select>
    </FormField>
  )
}
