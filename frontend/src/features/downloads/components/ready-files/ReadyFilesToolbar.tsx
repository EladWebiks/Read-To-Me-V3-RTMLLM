import { Button } from '@/shared/ui'

type Props = {
  cleaning: boolean
  canClean: boolean
  onRefresh: () => void
  onClean: () => void
  onClose: () => void
}

export function ReadyFilesToolbar(props: Props) {
  return (
    <div className="flex flex-wrap gap-2">
      <Button variant="outline" size="sm" onClick={props.onRefresh}>
        Refresh
      </Button>
      <Button
        variant="destructive"
        size="sm"
        disabled={props.cleaning || !props.canClean}
        onClick={props.onClean}
      >
        {props.cleaning ? 'Cleaning…' : 'Clean all'}
      </Button>
      <Button variant="outline" size="sm" className="ml-auto" onClick={props.onClose}>
        Close
      </Button>
    </div>
  )
}
