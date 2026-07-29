import type { NavigateFunction } from 'react-router'
import type { ClientAction } from '../api/chatApi'
import { shouldAutoNavigate } from './navigatePolicy'
import { applySettingsPatch } from './settingsActions'

/** Apply a validated server-originated client action. */
export function applyClientAction(
  action: ClientAction,
  pathname: string,
  navigate: NavigateFunction,
  setTheme: (theme: 'light' | 'dark' | 'system') => void,
): void {
  if (action.type === 'settings') {
    applySettingsPatch(action.settings, setTheme)
    return
  }
  if (action.type === 'download') return
  if (!shouldAutoNavigate(action, pathname)) return
  if (action.type === 'play') {
    void navigate(action.path, {
      state: { autoPlay: true, playbackRequestId: crypto.randomUUID() },
    })
    return
  }
  void navigate(action.path)
}
