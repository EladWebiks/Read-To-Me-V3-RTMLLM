import { useState } from 'react'
import type { EffectiveSetting } from '@/features/admin/api/settings'
import { useSetSetting } from '@/features/admin/hooks/useAdminSettings'
import { formatValue, parseValue } from '@/features/admin/logic/settingValue'
import {
  Button,
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  FormError,
  Input,
} from '@/shared/ui'

export function SettingEditDialog({
  setting,
  open,
  onOpenChange,
}: {
  setting: EffectiveSetting
  open: boolean
  onOpenChange: (open: boolean) => void
}) {
  const draft = useSettingDraft(setting)
  const save = useSetSetting()

  const submit = () => {
    save.mutate(
      { key: setting.key, value: parseValue(draft.text) },
      { onSuccess: () => onOpenChange(false) },
    )
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Edit setting</DialogTitle>
          <p className="font-mono text-xs text-muted-foreground">{setting.key}</p>
          {setting.description ? (
            <p className="text-sm text-muted-foreground">{setting.description}</p>
          ) : null}
        </DialogHeader>
        <SettingValueFields
          setting={setting}
          text={draft.text}
          onChange={draft.setText}
        />
        <FormError className="mt-2" error={save.error} />
        <div className="mt-4 flex justify-end gap-2">
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={() => onOpenChange(false)}
          >
            Cancel
          </Button>
          <Button type="button" size="sm" disabled={save.isPending} onClick={submit}>
            {save.isPending ? 'Saving…' : 'Save'}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  )
}

function useSettingDraft(setting: EffectiveSetting) {
  const [text, setText] = useState(formatValue(setting.effective_value))
  const [draftKey, setDraftKey] = useState(setting.key)
  if (setting.key !== draftKey) {
    setDraftKey(setting.key)
    setText(formatValue(setting.effective_value))
  }
  return { text, setText }
}

function SettingValueFields({
  setting,
  text,
  onChange,
}: {
  setting: EffectiveSetting
  text: string
  onChange: (value: string) => void
}) {
  return (
    <>
      <label className="block space-y-1.5">
        <span className="text-sm font-medium">Value</span>
        <Input
          className="font-mono"
          value={text}
          onChange={(event) => onChange(event.target.value)}
          aria-label={`Value for ${setting.key}`}
        />
      </label>
      <p className="mt-2 text-xs text-muted-foreground">
        Env default: <span className="font-mono">{formatValue(setting.env_value)}</span>
      </p>
    </>
  )
}
