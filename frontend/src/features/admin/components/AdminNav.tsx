import { NavLink } from 'react-router'

const LINKS = [
  { to: '/admin/users', label: 'Users' },
  { to: '/admin/settings', label: 'Settings' },
  { to: '/admin/usage', label: 'AI Usage' },
  { to: '/admin/catalog', label: 'LLM Catalog' },
  { to: '/admin/tool-calls', label: 'Tool Calls' },
  { to: '/admin/jobs', label: 'Jobs' },
]

export function AdminNav() {
  return (
    <nav
      className="w-full shrink-0 space-y-1 text-sm sm:w-44"
      aria-label="Admin sections"
    >
      {LINKS.map(({ to, label }) => (
        <NavLink
          key={to}
          to={to}
          className={({ isActive }) =>
            `block rounded-md px-3 py-1.5 transition-colors ${
              isActive
                ? 'bg-muted font-medium text-foreground'
                : 'text-muted-foreground hover:bg-muted/60 hover:text-foreground'
            }`
          }
        >
          {label}
        </NavLink>
      ))}
    </nav>
  )
}
