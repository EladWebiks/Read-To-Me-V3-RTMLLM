import { Outlet } from 'react-router'
import { AdminNav } from './AdminNav'

export function AdminLayout() {
  return (
    <div className="flex min-h-0 flex-1 flex-col gap-4 overflow-hidden sm:flex-row sm:gap-6">
      <AdminNav />
      <div className="flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden">
        <Outlet />
      </div>
    </div>
  )
}
