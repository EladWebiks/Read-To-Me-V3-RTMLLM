import { Navigate, Outlet } from 'react-router'
import { isUnauthorized, useMe } from '@/features/auth/hooks'

export function PublicOnlyRoute() {
  const { data, isLoading, isError, error } = useMe()

  if (isLoading) {
    return <p className="p-8 text-sm text-stone-500">Checking session…</p>
  }

  if (data?.user && !(isError && isUnauthorized(error))) {
    return <Navigate to="/reader" replace />
  }

  return <Outlet />
}
