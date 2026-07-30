import { useQuery } from '@tanstack/react-query'
import { fetchToolCalls, type ToolCallFilterValues } from '@/features/admin/api/toolCalls'

export function useToolCalls(
  filters: ToolCallFilterValues,
  limit: number,
  offset: number,
) {
  return useQuery({
    queryKey: ['admin', 'tool-calls', filters, limit, offset],
    queryFn: () => fetchToolCalls(filters, limit, offset),
  })
}
