import { Input } from '@/shared/ui'
import type { useEpubImport } from '../hooks/useEpubImport'
import { EpubField } from './EpubImportBits'

type State = ReturnType<typeof useEpubImport>

export function EpubMetaFields({ state }: { state: State }) {
  return (
    <>
      <div className="grid grid-cols-2 gap-3">
        <EpubField label="Title">
          <Input
            value={state.title}
            onChange={(e) => state.setTitle(e.target.value)}
            placeholder="From EPUB"
            disabled={state.importing}
          />
        </EpubField>
        <EpubField label="Author">
          <Input
            value={state.author}
            onChange={(e) => state.setAuthor(e.target.value)}
            placeholder="From EPUB"
            disabled={state.importing}
          />
        </EpubField>
      </div>
      <EpubField label="Starting chapter" hint="Sequential from this number.">
        <Input
          type="number"
          min={1}
          value={state.startingChapter}
          onChange={(e) => state.setStartingChapter(e.target.value)}
          disabled={state.importing}
          className="w-28"
        />
      </EpubField>
    </>
  )
}
