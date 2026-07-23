import { Input, Label } from '@/shared/ui'

type Props = {
  title: string
  setTitle: (v: string) => void
  author: string
  setAuthor: (v: string) => void
  starting: string
  setStarting: (v: string) => void
  showStarting: boolean
  onCoverChange: (file: File | null) => void
}

export function BookFormFields(props: Props) {
  return (
    <>
      <div className="space-y-2">
        <Label htmlFor="nb-title">Title</Label>
        <Input
          id="nb-title"
          value={props.title}
          onChange={(e) => props.setTitle(e.target.value)}
          required
        />
      </div>
      <div className="space-y-2">
        <Label htmlFor="nb-author">Author</Label>
        <Input
          id="nb-author"
          value={props.author}
          onChange={(e) => props.setAuthor(e.target.value)}
        />
      </div>
      {props.showStarting ? (
        <div className="space-y-2">
          <Label htmlFor="nb-start">Starting chapter number</Label>
          <Input
            id="nb-start"
            type="number"
            min={1}
            value={props.starting}
            onChange={(e) => props.setStarting(e.target.value)}
          />
        </div>
      ) : null}
      <div className="space-y-2">
        <Label htmlFor="nb-cover">Cover image</Label>
        <Input
          id="nb-cover"
          type="file"
          accept="image/*"
          onChange={(e) => props.onCoverChange(e.target.files?.[0] ?? null)}
        />
      </div>
    </>
  )
}
