import type { ReactNode } from 'react'
import { cn } from '@/shared/lib/cn'
import { FormError } from './form-error'
import { Label } from './label'

type Props = {
  id: string
  label: ReactNode
  hint?: ReactNode
  error?: string | Error | null
  className?: string
  children: ReactNode
}

/** Label + hint + error around a control the CALLER renders (textarea, file…).
 *
 * Emits `${id}-hint` / `${id}-error`; wire them to the control with
 * `describedBy` from ./field-aria (TextField does all of this automatically).
 */
export function FormField({ id, label, hint, error, className, children }: Props) {
  return (
    <div className={cn('space-y-1', className)}>
      <Label htmlFor={id}>{label}</Label>
      {children}
      {hint != null ? (
        <p id={`${id}-hint`} className="text-xs text-muted-foreground">
          {hint}
        </p>
      ) : null}
      <FormError id={`${id}-error`} error={error} />
    </div>
  )
}
