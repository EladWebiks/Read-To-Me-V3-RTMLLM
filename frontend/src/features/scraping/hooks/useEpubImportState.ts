import { useEffect, useState } from 'react'
import type { EpubImportResult, ImportJob } from '../types/importTypes'

export function useEpubFormFields() {
  const [files, setFiles] = useState<File[]>([])
  const [title, setTitle] = useState('')
  const [author, setAuthor] = useState('')
  const [startingChapter, setStartingChapter] = useState('1')
  return {
    files,
    setFiles,
    title,
    setTitle,
    author,
    setAuthor,
    startingChapter,
    setStartingChapter,
    resetFields: () => {
      setFiles([])
      setTitle('')
      setAuthor('')
      setStartingChapter('1')
    },
  }
}

export function useEpubJobState() {
  const [importJob, setImportJob] = useState<ImportJob | null>(null)
  const [importStartedAt, setImportStartedAt] = useState<number | null>(null)
  const [elapsedMs, setElapsedMs] = useState(0)
  const [cancelling, setCancelling] = useState(false)
  const [result, setResult] = useState<EpubImportResult | null>(null)
  const [importError, setImportError] = useState('')
  return {
    importJob,
    setImportJob,
    importStartedAt,
    setImportStartedAt,
    elapsedMs,
    setElapsedMs,
    cancelling,
    setCancelling,
    result,
    setResult,
    importError,
    setImportError,
    startSetters: {
      setImportError,
      setResult,
      setCancelling,
      setImportStartedAt,
      setElapsedMs,
      setImportJob,
    },
    resetJob: () => {
      setImportJob(null)
      setImportStartedAt(null)
      setElapsedMs(0)
      setCancelling(false)
      setResult(null)
      setImportError('')
    },
  }
}

export function useElapsed(
  importing: boolean,
  importStartedAt: number | null,
  setElapsedMs: (n: number) => void,
) {
  useEffect(() => {
    if (!importing || importStartedAt == null) return
    const id = setInterval(() => setElapsedMs(Date.now() - importStartedAt), 1000)
    return () => clearInterval(id)
  }, [importing, importStartedAt, setElapsedMs])
}
