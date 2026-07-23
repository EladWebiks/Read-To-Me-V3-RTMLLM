import { Navigate, Outlet, useLocation } from 'react-router'
import { isUnauthorized, useMe } from '@/features/auth/hooks'

export function ProtectedRoute() {
  const location = useLocation()
  const { data, isLoading, isError, error } = useMe()

  if (isLoading) {
    return <p className="p-8 text-sm text-stone-500">Checking session…</p>
  }

  if (isError && isUnauthorized(error)) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />
  }

  if (!data?.user) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />
  }

  return <Outlet />
}
