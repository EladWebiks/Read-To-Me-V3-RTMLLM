import { useState } from 'react'
import { Button } from '@/shared/ui'

/** Compact copy control for truncated/long emails in the users table. */
export function CopyEmailButton({ email }: { email: string }) {
  const [copied, setCopied] = useState(false)

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(email)
      setCopied(true)
      window.setTimeout(() => setCopied(false), 1200)
    } catch {
      setCopied(false)
    }
  }

  return (
    <Button
      type="button"
      variant="ghost"
      size="sm"
      className="h-6 shrink-0 px-1.5 text-[11px]"
      onClick={() => void copy()}
      aria-label={copied ? 'Copied' : `Copy ${email}`}
      title={email}
    >
      {copied ? 'Copied' : 'Copy'}
    </Button>
  )
}
