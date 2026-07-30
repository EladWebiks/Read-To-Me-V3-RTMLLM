import { useMe } from './hooks'

export function useIsAdmin(): boolean {
  const { data } = useMe()
  return data?.user?.is_admin === true
}
