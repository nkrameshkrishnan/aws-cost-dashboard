/**
 * Custom hook for table pagination logic.
 */
import { useState, useMemo } from 'react'

interface UsePaginationProps<T> {
  data: T[]
  initialItemsPerPage?: number
}

interface UsePaginationReturn<T> {
  currentPage: number
  itemsPerPage: number
  totalPages: number
  paginatedData: T[]
  setCurrentPage: (page: number) => void
  setItemsPerPage: (itemsPerPage: number) => void
  resetPagination: () => void
}

export function usePagination<T>({
  data,
  initialItemsPerPage = 10,
}: UsePaginationProps<T>): UsePaginationReturn<T> {
  const [currentPage, setCurrentPage] = useState(1)
  const [itemsPerPage, setItemsPerPageState] = useState(initialItemsPerPage)

  const totalPages = Math.ceil(data.length / itemsPerPage)

  // Paginated data
  const paginatedData = useMemo(() => {
    const startIndex = (currentPage - 1) * itemsPerPage
    const endIndex = startIndex + itemsPerPage
    return data.slice(startIndex, endIndex)
  }, [data, currentPage, itemsPerPage])

  // Handle page change
  const handlePageChange = (page: number) => {
    if (page >= 1 && page <= totalPages) {
      setCurrentPage(page)
    }
  }

  // Handle items per page change
  const setItemsPerPage = (newItemsPerPage: number) => {
    setItemsPerPageState(newItemsPerPage)
    // Reset to page 1 when changing items per page
    setCurrentPage(1)
  }

  // Reset pagination
  const resetPagination = () => {
    setCurrentPage(1)
    setItemsPerPageState(initialItemsPerPage)
  }

  // Auto-adjust current page if it exceeds total pages
  if (currentPage > totalPages && totalPages > 0) {
    setCurrentPage(totalPages)
  }

  return {
    currentPage,
    itemsPerPage,
    totalPages,
    paginatedData,
    setCurrentPage: handlePageChange,
    setItemsPerPage,
    resetPagination,
  }
}
