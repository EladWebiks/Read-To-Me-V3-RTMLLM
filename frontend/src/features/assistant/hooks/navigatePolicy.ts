import type { ClientAction } from '../api/chatApi'

/** Auto-open reader on play/resume when the user is not already there. */
export function shouldAutoNavigate(action: ClientAction, currentPath: string): boolean {
  if (action.type !== 'navigate') return false
  if (!action.path.startsWith('/read/')) return false
  return stripTrailingSlash(action.path) !== stripTrailingSlash(currentPath)
}

function stripTrailingSlash(path: string): string {
  if (path.length > 1 && path.endsWith('/')) return path.slice(0, -1)
  return path
}
