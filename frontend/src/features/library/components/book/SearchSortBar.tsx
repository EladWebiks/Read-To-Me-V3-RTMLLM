import { Button, Input } from '@/shared/ui'
import type { LibrarySort } from '@/features/library/types'

const SORTS: { id: LibrarySort; label: string }[] = [
  { id: 'read', label: 'Last read' },
  { id: 'added', label: 'Added' },
  { id: 'name', label: 'Name' },
  { id: 'chapters', label: 'Chapters' },
]

type Props = {
  search: string
  onSearch: (value: string) => void
  sort: LibrarySort
  onSort: (value: LibrarySort) => void
  onNewBook: () => void
}

export function SearchSortBar(props: Props) {
  return (
    <div className="flex flex-wrap items-center gap-3">
      <Input
        placeholder="Search books…"
        value={props.search}
        onChange={(e) => props.onSearch(e.target.value)}
        className="max-w-sm"
      />
      <div className="flex flex-wrap gap-1">
        {SORTS.map((item) => (
          <Button
            key={item.id}
            type="button"
            size="sm"
            variant={props.sort === item.id ? 'default' : 'outline'}
            onClick={() => props.onSort(item.id)}
          >
            {item.label}
          </Button>
        ))}
      </div>
      <Button type="button" size="sm" className="ml-auto" onClick={props.onNewBook}>
        New Book
      </Button>
    </div>
  )
}
