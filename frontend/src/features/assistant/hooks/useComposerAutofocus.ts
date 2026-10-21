import { type RefObject, useEffect, useRef } from 'react'

/** Restore composer focus after a send finishes (disabled inputs drop focus). */
export function useComposerAutofocus(
  inputRef: RefObject<HTMLTextAreaElement | null>,
  sending: boolean,
  locked: boolean,
): void {
  const wasSending = useRef(false)
  useEffect(() => {
    const finished = wasSending.current && !sending
    wasSending.current = sending
    if (finished && !locked) inputRef.current?.focus()
  }, [sending, locked, inputRef])
}
