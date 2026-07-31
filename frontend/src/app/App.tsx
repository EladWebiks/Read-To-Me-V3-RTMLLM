import { BrowserRouter, Navigate, Route, Routes, useParams } from 'react-router'
import {
  AdminLayout,
  CatalogPage,
  JobsPage,
  SettingsPage,
  ToolCallsPage,
  UsagePage,
  UsersPage,
} from '@/features/admin'
import { LoginPage, ProtectedRoute, PublicOnlyRoute, RequireAdmin } from '@/features/auth'
import { ChapterEditorPage, ChapterNewPage, LibraryPage } from '@/features/library'
import { libraryBookHref } from '@/features/library/logic/libraryPaths'
import { ReaderHubPage, ReaderPage, ResumeReadingPage } from '@/features/reader'
import { ScraperPage } from '@/features/scraping'
import { AppShell } from '@/layout/AppShell'

function LegacyBookDetailRedirect() {
  const { bookId = '' } = useParams()
  return <Navigate to={libraryBookHref(bookId)} replace />
}

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
            <Route path="/library/books/:bookId" element={<LegacyBookDetailRedirect />} />
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
            <Route element={<RequireAdmin />}>
              <Route path="/admin" element={<AdminLayout />}>
                <Route index element={<Navigate to="/admin/users" replace />} />
                <Route path="users" element={<UsersPage />} />
                <Route path="settings" element={<SettingsPage />} />
                <Route path="usage" element={<UsagePage />} />
                <Route path="catalog" element={<CatalogPage />} />
                <Route path="tool-calls" element={<ToolCallsPage />} />
                <Route path="jobs" element={<JobsPage />} />
              </Route>
            </Route>
          </Route>
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
