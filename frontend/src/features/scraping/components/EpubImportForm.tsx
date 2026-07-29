import { Upload } from 'lucide-react'
import { Button } from '@/shared/ui'
import { cn } from '@/shared/lib/cn'
import type { useEpubImport } from '../hooks/useEpubImport'
import { EpubImportSuccess } from './EpubImportBits'
import { EpubFileList } from './EpubFileList'
import { EpubImportProgress } from './EpubImportProgress'
import { EpubMetaFields } from './EpubMetaFields'

type State = ReturnType<typeof useEpubImport>
type Props = { state: State; onPickFile: () => void; onClose: () => void }

export function EpubImportForm({ state, onPickFile, onClose }: Props) {
  const done = state.result != null

  return (
    <>
      <div className="min-h-0 flex-1 space-y-4 overflow-y-auto px-5 py-4">
        <Body state={state} onPickFile={onPickFile} />
        {state.importError ? (
          <p
            className={cn(
              'rounded-md px-3 py-2 text-sm',
              state.importJob?.status === 'cancelled'
                ? 'bg-amber-500/10 text-amber-600'
                : 'bg-destructive/10 text-destructive',
            )}
          >
            {state.importError}
          </p>
        ) : null}
      </div>
      <div className="flex shrink-0 justify-end gap-2 border-t border-border px-5 py-3">
        <Button
          type="button"
          variant="ghost"
          onClick={onClose}
          disabled={state.importing}
        >
          {done ? 'Done' : 'Close'}
        </Button>
        {done ? null : (
          <Button
            type="button"
            className="gap-1.5"
            disabled={state.importing || state.files.length === 0}
            onClick={() => void state.startImport()}
          >
            <Upload className="size-4" />
            {state.importing ? 'Importing…' : 'Import'}
          </Button>
        )}
      </div>
    </>
  )
}

function Body({ state, onPickFile }: { state: State; onPickFile: () => void }) {
  if (state.result) return <EpubImportSuccess result={state.result} />
  if (state.importJob?.status === 'running') {
    return (
      <EpubImportProgress
        job={state.importJob}
        elapsedMs={state.elapsedMs}
        cancelling={state.cancelling}
        onCancel={() => void state.cancelImport()}
      />
    )
  }
  return (
    <>
      <EpubFileList
        files={state.files}
        importing={state.importing}
        onAddClick={onPickFile}
        onClear={state.clearFiles}
        onRemove={state.removeFile}
        onMove={state.moveFile}
      />
      <EpubMetaFields state={state} />
    </>
  )
}
