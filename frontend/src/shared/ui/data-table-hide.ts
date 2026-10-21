export type DataTableHideBelow = 'sm' | 'md' | 'lg'

export const DATA_TABLE_HIDE: Record<DataTableHideBelow, string> = {
  sm: 'hidden sm:table-cell',
  md: 'hidden md:table-cell',
  lg: 'hidden lg:table-cell',
}
