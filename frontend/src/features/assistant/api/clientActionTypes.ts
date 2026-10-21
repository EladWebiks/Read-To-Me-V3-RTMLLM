type NavigateClientAction = {
  type: 'navigate' | 'play'
  path: string
  label: string
}

export type UiSettingsPatch = {
  theme?: 'light' | 'dark' | 'system'
  font_size?: number
  max_playback_rate?: number
  playback_rate?: number
  playback_engine?: 'browser' | 'server'
  tts_provider?: 'edge' | 'sapi'
  voice?: string
  highlighting?: 'auto' | 'word' | 'paragraph'
}

type SettingsClientAction = {
  type: 'settings'
  label: string
  settings: UiSettingsPatch
}

export type DownloadClientAction = {
  type: 'download'
  label: string
  jobId: string
  bookId: string
  chapterFrom: number
  chapterTo: number
}

export type ScrapeClientAction = {
  type: 'scrape'
  label: string
  jobId: string
  maxChapters: number | null
  chapterFrom: number | null
}

export type ClientAction =
  NavigateClientAction | SettingsClientAction | DownloadClientAction | ScrapeClientAction
