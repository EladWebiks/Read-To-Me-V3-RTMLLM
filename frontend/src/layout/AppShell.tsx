import { useEffect } from 'react'
import { Link, Outlet, useLocation } from 'react-router'
import { AssistantHost } from '@/features/assistant'
import { useLibraryLiveDuringScrapes } from '@/features/scraping/hooks'
import { ShellActions } from './ShellActions'
import { ShellNavLinks } from './ShellNav'

export function AppShell() {
  const { pathname } = useLocation()
  const isReading = pathname.startsWith('/read/')
  useReaderScrollLock(isReading)
  useLibraryLiveDuringScrapes()

  return (
    <div
      className={
        isReading
          ? 'flex h-dvh flex-col overflow-hidden bg-background text-foreground'
          : 'min-h-screen bg-background text-foreground'
      }
    >
      <header
        className={`z-40 shrink-0 border-b border-border/80 bg-background/90 backdrop-blur-sm ${
          isReading ? '' : 'sticky top-0'
        }`}
      >
        <div className="flex w-full items-center justify-between gap-3 px-4 py-3">
          <Link to="/library" className="text-lg font-semibold tracking-tight">
            RTM
          </Link>
          <div className="flex items-center gap-1 sm:gap-2">
            <ShellNavLinks readerActive={pathname === '/reader' || isReading} />
            <ShellActions />
          </div>
        </div>
      </header>
      <main
        className={
          isReading
            ? 'mx-auto flex min-h-0 w-full flex-1 flex-col overflow-hidden px-3 py-2 sm:px-4 sm:py-3'
            : 'mx-auto w-full max-w-5xl px-4 py-4 sm:py-6'
        }
      >
        <Outlet />
      </main>
      <AssistantHost />
    </div>
  )
}

/** Prevent document scroll on reader — only the chapter pane should scroll. */
function useReaderScrollLock(locked: boolean) {
  useEffect(() => {
    if (!locked) return
    const html = document.documentElement
    const { body } = document
    const prevHtml = html.style.overflow
    const prevBody = body.style.overflow
    html.style.overflow = 'hidden'
    body.style.overflow = 'hidden'
    return () => {
      html.style.overflow = prevHtml
      body.style.overflow = prevBody
    }
  }, [locked])
}
