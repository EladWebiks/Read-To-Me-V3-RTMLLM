import { useRef } from 'react'
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/shared/ui'
import { useEpubImport } from '../hooks/useEpubImport'
import { EpubImportForm } from './EpubImportForm'

type Props = { open: boolean; onClose: () => void; onImported: () => void }

export function UploadEpubDialog({ open, onClose, onImported }: Props) {
  const fileInputRef = useRef<HTMLInputElement>(null)
  const state = useEpubImport(onImported)

  function handleClose() {
    if (state.importing) return
    state.reset()
    if (fileInputRef.current) fileInputRef.current.value = ''
    onClose()
  }

  return (
    <Dialog open={open} onOpenChange={(next) => !next && handleClose()}>
      <DialogContent className="flex max-h-[min(85vh,40rem)] flex-col gap-0 overflow-hidden p-0 sm:max-w-md">
        <DialogHeader className="shrink-0 border-b border-border px-5 pb-3 pt-5">
          <DialogTitle>Upload EPUB</DialogTitle>
        </DialogHeader>
        <input
          ref={fileInputRef}
          type="file"
          accept=".epub"
          hidden
          onChange={(e) => {
            const file = e.target.files?.[0]
            if (fileInputRef.current) fileInputRef.current.value = ''
            if (file) state.addFile(file)
          }}
        />
        <EpubImportForm
          state={state}
          onPickFile={() => fileInputRef.current?.click()}
          onClose={handleClose}
        />
      </DialogContent>
    </Dialog>
  )
}
