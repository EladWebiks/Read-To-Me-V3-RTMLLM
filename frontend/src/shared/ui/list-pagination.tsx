import {
  Pagination,
  PaginationContent,
  PaginationEllipsis,
  PaginationItem,
  PaginationLink,
  PaginationNext,
  PaginationPrevious,
} from '@/shared/ui/pagination'
import { pageWindow } from '@/shared/lib/pageWindow'

type Props = {
  page: number
  pageCount: number
  total: number
  pageSize: number
  onPage: (page: number) => void
}

/** Shared list pager (library, scraper jobs, etc.). */
export function ListPagination(props: Props) {
  const from = props.total === 0 ? 0 : (props.page - 1) * props.pageSize + 1
  const to = Math.min(props.page * props.pageSize, props.total)
  const pages = pageWindow(props.page, props.pageCount)

  return (
    <div className="flex min-h-12 flex-col items-center justify-between gap-3 border-t border-border pt-3 sm:flex-row">
      <p className="text-sm text-muted-foreground">
        Showing <span className="font-medium text-foreground">{from}</span>–
        <span className="font-medium text-foreground">{to}</span> of{' '}
        <span className="font-medium text-foreground">{props.total}</span>
      </p>
      {props.pageCount > 1 ? (
        <Pagination className="mx-0 w-auto justify-end">
          <PaginationContent>
            <PaginationItem>
              <PaginationPrevious
                disabled={props.page <= 1}
                onClick={() => props.onPage(props.page - 1)}
              />
            </PaginationItem>
            {pages.map((item, index) =>
              item === '…' ? (
                <PaginationItem key={`gap-${index}`}>
                  <PaginationEllipsis />
                </PaginationItem>
              ) : (
                <PaginationItem key={item}>
                  <PaginationLink
                    isActive={item === props.page}
                    onClick={() => props.onPage(item)}
                  >
                    {item}
                  </PaginationLink>
                </PaginationItem>
              ),
            )}
            <PaginationItem>
              <PaginationNext
                disabled={props.page >= props.pageCount}
                onClick={() => props.onPage(props.page + 1)}
              />
            </PaginationItem>
          </PaginationContent>
        </Pagination>
      ) : null}
    </div>
  )
}
