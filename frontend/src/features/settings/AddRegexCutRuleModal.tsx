import { useMemo, useState } from 'react'
import {
  Button,
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  TextField,
} from '@/shared/ui'

export type AddRegexCutRuleModalProps = {
  open: boolean
  onOpenChange: (open: boolean) => void
  onAdd: (pattern: string) => void
}

export function AddRegexCutRuleModal({
  open,
  onOpenChange,
  onAdd,
}: AddRegexCutRuleModalProps) {
  const [pattern, setPattern] = useState('')

  const validate = useMemo((): string | null => {
    const p = pattern.trim()
    if (!p) return 'Required'
    try {
      new RegExp(p, 'gms')
      return null
    } catch {
      return 'Invalid regex syntax'
    }
  }, [pattern])

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Regex cutting rule</DialogTitle>
        </DialogHeader>
        <RegexCutRuleForm
          pattern={pattern}
          onChange={setPattern}
          validate={validate}
          onCancel={() => onOpenChange(false)}
          onAdd={() => {
            if (!open || validate) return
            onAdd(pattern.trim())
            onOpenChange(false)
          }}
        />
      </DialogContent>
    </Dialog>
  )
}

function RegexCutRuleForm(props: {
  pattern: string
  onChange: (v: string) => void
  validate: string | null
  onCancel: () => void
  onAdd: () => void
}) {
  const canAdd = props.pattern.trim().length > 0 && props.validate == null
  return (
    <div className="space-y-3">
      <TextField
        id="regex-cut-pattern"
        label="Regex pattern"
        hint="JS RegExp pattern (applied with flags gms)."
        error={props.validate ?? undefined}
        value={props.pattern}
        onChange={(e) => props.onChange(e.currentTarget.value)}
        onInput={(e) => props.onChange(e.currentTarget.value)}
      />

      <div className="flex justify-end gap-2">
        <Button type="button" variant="outline" onClick={props.onCancel}>
          Cancel
        </Button>
        <Button type="button" disabled={!canAdd} onClick={props.onAdd}>
          Add
        </Button>
      </div>
    </div>
  )
}
