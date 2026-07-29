import { matchPath, useLocation } from 'react-router'

export type UiContext = {
  path: string
  bookId?: string
  chapterId?: string
}

/** Current SPA route for chat grounding (ADR-14). */
export function useUiContext(): UiContext {
  const { pathname } = useLocation()
  const withChapter = matchPath('/read/:bookId/:chapterId', pathname)
  if (withChapter?.params.bookId && withChapter.params.chapterId) {
    return {
      path: pathname,
      bookId: withChapter.params.bookId,
      chapterId: withChapter.params.chapterId,
    }
  }
  const bookOnly = matchPath('/read/:bookId', pathname)
  if (bookOnly?.params.bookId) {
    return { path: pathname, bookId: bookOnly.params.bookId }
  }
  return { path: pathname }
}

export function uiContextPayload(ctx: UiContext): {
  path: string
  book_id?: string
  chapter_id?: string
} {
  return {
    path: ctx.path,
    ...(ctx.bookId ? { book_id: ctx.bookId } : {}),
    ...(ctx.chapterId ? { chapter_id: ctx.chapterId } : {}),
  }
}
