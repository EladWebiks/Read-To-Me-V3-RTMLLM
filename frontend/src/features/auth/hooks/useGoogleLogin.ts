import { useCallback, useEffect, useRef, useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router'
import { fetchMe, GOOGLE_LOGIN_URL } from '@/features/auth/api'
import { openGooglePopup, type PopupResult } from '@/features/auth/logic/googlePopup'
import { meQueryKey } from './hooks'

// Reconciliation probe for the COOP path (see googlePopup.ts): once the popup
// looks closed, only the session cookie can tell success from abandonment.
function checkSession(): Promise<boolean> {
  return fetchMe().then(
    () => true,
    () => false,
  )
}

export type GoogleLoginState =
  { status: 'idle' | 'pending' } | { status: 'error'; reason: string }

export function useGoogleLogin() {
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  const [state, setState] = useState<GoogleLoginState>({ status: 'idle' })
  const cleanupRef = useRef<(() => void) | null>(null)

  useEffect(() => () => cleanupRef.current?.(), [])

  const start = useCallback(() => {
    cleanupRef.current?.()
    setState({ status: 'pending' })
    cleanupRef.current = openGooglePopup(
      GOOGLE_LOGIN_URL,
      checkSession,
      (result: PopupResult) => {
        if (result.status === 'success') {
          // resetQueries, not invalidateQueries: on this page the `me` query is
          // already cached in `status: 'error'` (401). Invalidation only starts a
          // refetch and leaves the error in place, so the ProtectedRoute mounted
          // by the navigate below sees isLoading === false / isError === true and
          // bounces straight back to /login until the refetch lands. Resetting
          // clears the cached error synchronously, putting the guard into its
          // "Checking session…" branch instead.
          void queryClient.resetQueries({ queryKey: meQueryKey })
          void navigate('/reader', { replace: true })
          return
        }
        setState({ status: 'error', reason: result.reason })
      },
    )
  }, [navigate, queryClient])

  return { state, start }
}
