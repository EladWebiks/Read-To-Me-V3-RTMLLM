import { useQuery } from '@tanstack/react-query'
import { apiGet } from '@/shared/lib/api'

type HealthResponse = {
  status: string
  service: string
}

export function useHealth() {
  return useQuery({
    queryKey: ['health'],
    queryFn: () => apiGet<HealthResponse>('/api/health'),
    retry: false,
  })
}
