import type { InputHTMLAttributes, ReactNode } from 'react'
import { cn } from '@/shared/lib/cn'
import { describedBy } from './field-aria'
import { FormField } from './form-field'
import { Input } from './input'

type Props = Omit<InputHTMLAttributes<HTMLInputElement>, 'id' | 'size'> & {
  id: string
  label: ReactNode
  hint?: ReactNode
  error?: string | Error | null
  /** Decimal inputMode + tabular numerals (admin numeric fields). */
  numeric?: boolean
}

/** Label + Input + hint + error as one unit, with the ARIA wiring done. */
export function TextField({
  id,
  label,
  hint,
  error,
  numeric = false,
  className,
  inputMode,
  ...props
}: Props) {
  const hasError = error != null && error !== ''
  return (
    <FormField id={id} label={label} hint={hint} error={error}>
      <Input
        {...props}
        id={id}
        inputMode={numeric ? 'decimal' : inputMode}
        aria-invalid={hasError ? true : undefined}
        aria-describedby={describedBy(id, hint != null, hasError)}
        className={cn(numeric && 'tabular-nums', className)}
      />
    </FormField>
  )
}
