import { QueryClient } from '@tanstack/react-query'

/** App-wide client — import this for non-React invalidation (e.g. SSE handlers). */
export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      retry: 1,
    },
  },
})
