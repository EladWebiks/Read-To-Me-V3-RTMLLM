import type { ReactNode } from 'react'
import { BookOpen, Library, ShieldCheck, Wand2 } from 'lucide-react'
import { NavLink } from 'react-router'
import { useIsAdmin } from '@/features/auth/hooks'

export function ShellNavLinks({ readerActive }: { readerActive: boolean }) {
  const isAdmin = useIsAdmin()
  return (
    <nav className="mr-1 flex items-center gap-1 text-sm">
      <ShellNav to="/library" label="Library" icon={<Library className="h-4 w-4" />} />
      <ShellNav
        to="/reader"
        label="Reader"
        icon={<BookOpen className="h-4 w-4" />}
        active={readerActive}
      />
      <ShellNav to="/scraper" label="Scraper" icon={<Wand2 className="h-4 w-4" />} />
      {isAdmin && (
        <ShellNav to="/admin" label="Admin" icon={<ShieldCheck className="h-4 w-4" />} />
      )}
    </nav>
  )
}

function ShellNav({
  to,
  label,
  icon,
  active,
}: {
  to: string
  label: string
  icon: ReactNode
  active?: boolean
}) {
  return (
    <NavLink
      to={to}
      className={({ isActive }) =>
        `inline-flex items-center gap-1.5 rounded-md px-2 py-1.5 transition-colors ${
          active || isActive
            ? 'bg-muted font-medium text-foreground'
            : 'text-muted-foreground hover:bg-muted/60 hover:text-foreground'
        }`
      }
    >
      {icon}
      <span className="hidden sm:inline">{label}</span>
    </NavLink>
  )
}
