import { useState } from 'react'
import { useNavigate } from 'react-router'
import type { User } from '@/features/auth/types'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/shared/ui'

type Props = { user: User; membershipLabel: string }

/** Navbar avatar: Google profile picture with an initial-letter fallback. */
export function UserAvatar({ user, membershipLabel }: Props) {
  const [broken, setBroken] = useState(false)
  const navigate = useNavigate()
  const showImage = Boolean(user.picture_url) && !broken
  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        aria-label="Account menu"
        className="rounded-full outline-none"
      >
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
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        <DropdownMenuLabel className="px-2.5 py-1.5 text-xs text-muted-foreground">
          {user.email ?? user.username}
          <span className="block">{membershipLabel} plan</span>
        </DropdownMenuLabel>
        <DropdownMenuSeparator className="my-1 h-px bg-border" />
        <DropdownMenuItem onSelect={() => navigate('/usage')}>
          Plan &amp; usage
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
