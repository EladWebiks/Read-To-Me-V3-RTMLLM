import { Navigate, Outlet } from 'react-router'
import { useMe } from '@/features/auth/hooks'

/** Nested inside ProtectedRoute: the session exists; only the flag is checked. */
export function RequireAdmin() {
  const { data, isLoading } = useMe()
  if (isLoading) {
    return <p className="p-8 text-sm text-muted-foreground">Checking access…</p>
  }
  if (!data?.user?.is_admin) {
    return <Navigate to="/" replace />
  }
  return <Outlet />
}
