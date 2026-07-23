import { useState } from 'react'
import { Settings } from 'lucide-react'
import { Button, Sheet, SheetContent, SheetHeader, SheetTitle } from '@/shared/ui'
import { SettingsFields } from './SettingsFields'

export function SettingsSheet() {
  const [open, setOpen] = useState(false)
  return (
    <>
      <Button
        type="button"
        variant="ghost"
        size="icon"
        aria-label="Settings"
        onClick={() => setOpen(true)}
      >
        <Settings className="h-4 w-4" />
      </Button>
      <Sheet open={open} onOpenChange={setOpen}>
        <SheetContent>
          <SheetHeader>
            <SheetTitle>Settings</SheetTitle>
          </SheetHeader>
          <SettingsFields />
        </SheetContent>
      </Sheet>
    </>
  )
}
