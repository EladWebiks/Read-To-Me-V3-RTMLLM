import { Outlet } from 'react-router'
import { AdminNav } from './AdminNav'

export function AdminLayout() {
  return (
    <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:gap-6">
      <AdminNav />
      <div className="min-w-0 flex-1">
        <Outlet />
      </div>
    </div>
  )
}
