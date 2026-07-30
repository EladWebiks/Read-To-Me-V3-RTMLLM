import { useState } from 'react'
import type { User } from '@/features/auth/types'
import { IconTooltip } from '@/shared/ui'

/** Navbar avatar: Google profile picture with an initial-letter fallback. */
export function UserAvatar({ user }: { user: User }) {
  const [broken, setBroken] = useState(false)
  const showImage = Boolean(user.picture_url) && !broken
  return (
    <IconTooltip label={user.email ?? user.username}>
      {showImage ? (
        <img
          src={user.picture_url ?? undefined}
          alt={user.username}
          referrerPolicy="no-referrer"
          className="h-7 w-7 shrink-0 rounded-full border border-border/70 object-cover"
          onError={() => setBroken(true)}
        />
      ) : (
        <span
          role="img"
          aria-label={user.username}
          className="flex h-7 w-7 shrink-0 select-none items-center justify-center rounded-full border border-border/70 bg-muted text-xs font-semibold uppercase text-muted-foreground"
        >
          {user.username.charAt(0)}
        </span>
      )}
    </IconTooltip>
  )
}
