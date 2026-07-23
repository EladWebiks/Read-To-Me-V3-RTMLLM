import { useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { Button, Label } from '@/shared/ui'

const API_BASE = import.meta.env.VITE_API_URL ?? ''

type Props = { bookId: string }

export function CoverUpload({ bookId }: Props) {
  const client = useQueryClient()
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  return (
    <div className="space-y-1">
      <Label htmlFor={`cover-${bookId}`}>Cover image</Label>
      <div className="flex flex-wrap items-center gap-2">
        <input
          id={`cover-${bookId}`}
          type="file"
          accept="image/*"
          className="text-sm"
          disabled={busy}
          onChange={(event) => {
            const file = event.target.files?.[0]
            if (!file) return
            setBusy(true)
            setError(null)
            void uploadCover(bookId, file)
              .then(() =>
                client.invalidateQueries({ queryKey: ['library', 'books', bookId] }),
              )
              .then(() => client.invalidateQueries({ queryKey: ['library', 'books'] }))
              .catch(() => setError('Upload failed'))
              .finally(() => setBusy(false))
          }}
        />
        {busy ? (
          <Button type="button" size="sm" variant="ghost" disabled>
            Uploading…
          </Button>
        ) : null}
      </div>
      {error ? <p className="text-xs text-destructive">{error}</p> : null}
    </div>
  )
}

async function uploadCover(bookId: string, file: File): Promise<void> {
  const body = new FormData()
  body.append('file', file)
  const response = await fetch(`${API_BASE}/api/library/books/${bookId}/cover`, {
    method: 'POST',
    credentials: 'include',
    body,
  })
  if (!response.ok) {
    throw new Error(`upload failed: ${response.status}`)
  }
}
