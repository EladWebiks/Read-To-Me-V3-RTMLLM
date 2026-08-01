import { cn } from '@/shared/lib/cn'

type Props = {
  error?: string | Error | null
  id?: string
  /** Render a <span>: for containers that only allow phrasing content. */
  inline?: boolean
  className?: string
}

/** Standard destructive error line; renders nothing when there is no error. */
export function FormError({ error, id, inline = false, className }: Props) {
  const message = typeof error === 'string' ? error : (error?.message ?? '')
  if (!message) return null
  const Tag = inline ? 'span' : 'p'
  return (
    <Tag id={id} role="alert" className={cn('text-xs text-destructive', className)}>
      {message}
    </Tag>
  )
}
