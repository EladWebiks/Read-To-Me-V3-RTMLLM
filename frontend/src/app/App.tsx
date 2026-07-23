import { BrowserRouter, Navigate, Route, Routes } from 'react-router'
import { LoginPage, ProtectedRoute, PublicOnlyRoute } from '@/features/auth'
import {
  BookDetailPage,
  ChapterEditorPage,
  ChapterNewPage,
  LibraryPage,
} from '@/features/library'
import { ReaderHubPage, ReaderPage, ResumeReadingPage } from '@/features/reader'
import { ScraperPage } from '@/features/scraping'
import { AppShell } from '@/layout/AppShell'

export function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<PublicOnlyRoute />}>
          <Route path="/login" element={<LoginPage />} />
        </Route>
        <Route element={<ProtectedRoute />}>
          <Route element={<AppShell />}>
            <Route path="/" element={<Navigate to="/reader" replace />} />
            <Route path="/library" element={<LibraryPage />} />
            <Route path="/library/books/:bookId" element={<BookDetailPage />} />
            <Route
              path="/library/books/:bookId/chapters/new"
              element={<ChapterNewPage />}
            />
            <Route
              path="/library/books/:bookId/chapters/:chapterId/edit"
              element={<ChapterEditorPage />}
            />
            <Route path="/reader" element={<ReaderHubPage />} />
            <Route path="/read/:bookId" element={<ResumeReadingPage />} />
            <Route path="/read/:bookId/:chapterId" element={<ReaderPage />} />
            <Route path="/scraper" element={<ScraperPage />} />
          </Route>
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
