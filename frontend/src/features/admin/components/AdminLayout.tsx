import { Outlet } from 'react-router'
import { AdminNav } from './AdminNav'

export function AdminLayout() {
  return (
    <div className="flex min-h-0 flex-col gap-4 sm:flex-row sm:items-stretch sm:gap-6">
      <AdminNav />
      <div className="min-h-0 min-w-0 flex-1">
        <Outlet />
      </div>
    </div>
  )
}
