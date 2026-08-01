/** Shared field ARIA helpers.
 *
 * Lives outside form-field.tsx because react-refresh/only-export-components
 * forbids a component file from also exporting plain functions.
 */

/** aria-describedby value for a field with this id; undefined when bare. */
export function describedBy(
  id: string,
  hasHint: boolean,
  hasError: boolean,
): string | undefined {
  const ids = [hasHint ? `${id}-hint` : null, hasError ? `${id}-error` : null]
  const present = ids.filter((part): part is string => part !== null)
  return present.length > 0 ? present.join(' ') : undefined
}
