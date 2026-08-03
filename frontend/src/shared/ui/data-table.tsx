import type { ReactNode, TdHTMLAttributes, ThHTMLAttributes } from 'react'
import { cn } from '@/shared/lib/cn'
import { DATA_TABLE_HIDE, type DataTableHideBelow } from './data-table-hide'

type TableProps = {
  children: ReactNode
  empty?: boolean
  emptyLabel?: ReactNode
  className?: string
}

/** Bordered, fixed-layout data table with optional empty state. */
export function DataTable({
  children,
  empty = false,
  emptyLabel,
  className,
}: TableProps) {
  if (empty) {
    return (
      <div className="rounded-lg border border-dashed border-border px-4 py-8 text-center text-sm text-muted-foreground">
        {emptyLabel ?? 'No results.'}
      </div>
    )
  }
  return (
    <div
      className={cn('overflow-hidden rounded-lg border border-border bg-card', className)}
    >
      <table className="w-full table-fixed text-left text-sm">{children}</table>
    </div>
  )
}

export function DataTableHeader({ children }: { children: ReactNode }) {
  return (
    <thead className="border-b border-border bg-muted/40 text-xs text-muted-foreground">
      <tr>{children}</tr>
    </thead>
  )
}

export function DataTableBody({ children }: { children: ReactNode }) {
  return <tbody>{children}</tbody>
}

type ColProps = ThHTMLAttributes<HTMLTableCellElement> & {
  hideBelow?: DataTableHideBelow
  srOnly?: boolean
}

export function DataTableColumn({
  children,
  className,
  hideBelow,
  srOnly,
  ...props
}: ColProps) {
  return (
    <th
      className={cn(
        'px-2.5 py-1.5 font-medium',
        hideBelow && DATA_TABLE_HIDE[hideBelow],
        className,
      )}
      {...props}
    >
      {srOnly ? <span className="sr-only">{children}</span> : children}
    </th>
  )
}

type CellProps = TdHTMLAttributes<HTMLTableCellElement> & {
  hideBelow?: DataTableHideBelow
}

export function DataTableCell({ children, className, hideBelow, ...props }: CellProps) {
  return (
    <td
      className={cn(
        'px-2.5 py-1 align-middle',
        hideBelow && DATA_TABLE_HIDE[hideBelow],
        className,
      )}
      {...props}
    >
      {children}
    </td>
  )
}
