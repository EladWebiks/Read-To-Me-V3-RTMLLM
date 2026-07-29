import { useQueryClient } from '@tanstack/react-query'
import { cancelEpubImport, moveFileItem, startEpubImport } from './epubImportActions'
import { useElapsed, useEpubFormFields, useEpubJobState } from './useEpubImportState'
import { useEpubImportPoll } from './useEpubImportPoll'

export function useEpubImport(onImported: () => void) {
  const queryClient = useQueryClient()
  const form = useEpubFormFields()
  const job = useEpubJobState()
  const importing = job.importJob?.status === 'running'

  useEpubImportPoll(job.importJob, {
    setImportJob: job.setImportJob,
    setResult: job.setResult,
    setImportError: job.setImportError,
    onImported,
  })
  useElapsed(importing, job.importStartedAt, job.setElapsedMs)

  return {
    ...form,
    ...job,
    importing,
    addFile: (file: File) => {
      form.setFiles((prev) => [...prev, file])
      job.setResult(null)
      job.setImportError('')
    },
    removeFile: (index: number) =>
      form.setFiles((prev) => prev.filter((_, i) => i !== index)),
    moveFile: (index: number, direction: -1 | 1) =>
      form.setFiles((prev) => moveFileItem(prev, index, direction)),
    clearFiles: () => form.setFiles([]),
    reset: () => {
      form.resetFields()
      job.resetJob()
    },
    startImport: () =>
      void startEpubImport({
        files: form.files,
        importing,
        title: form.title,
        author: form.author,
        startingChapter: form.startingChapter,
        ...job.startSetters,
        queryClient,
        onImported,
      }),
    cancelImport: () =>
      void cancelEpubImport(
        job.importJob,
        importing,
        job.setCancelling,
        job.setImportJob,
        job.setImportError,
      ),
  }
}
