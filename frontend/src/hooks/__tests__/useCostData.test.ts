import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { createElement, ReactNode } from 'react'
import { useCostSummary, useDailyCosts } from '../useCostData'
import { costsApi } from '@/api/costs'

// Mock the API module
vi.mock('@/api/costs', () => ({
  costsApi: {
    getSummary: vi.fn(),
    getDailyCosts: vi.fn(),
    getServiceBreakdown: vi.fn(),
  },
}))

const createWrapper = () => {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
        gcTime: 0,
      },
    },
  })
  return ({ children }: { children: ReactNode }) =>
    createElement(QueryClientProvider, { client: queryClient }, children)
}

describe('useCostSummary', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('fetches cost summary successfully', async () => {
    const mockData = {
      total_cost: 1000,
      period: 'monthly',
      currency: 'USD',
    }

    vi.mocked(costsApi.getSummary).mockResolvedValue(mockData)

    const { result } = renderHook(
      () => useCostSummary('default', '2024-01-01', '2024-01-31'),
      { wrapper: createWrapper() }
    )

    // Wait for data to load
    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true)
    })

    expect(result.current.data).toEqual(mockData)
    expect(costsApi.getSummary).toHaveBeenCalledWith('default', '2024-01-01', '2024-01-31')
  })

  it('handles errors correctly', async () => {
    const mockError = new Error('Failed to fetch costs')
    vi.mocked(costsApi.getSummary).mockRejectedValue(mockError)

    const { result } = renderHook(
      () => useCostSummary('default', '2024-01-01', '2024-01-31'),
      { wrapper: createWrapper() }
    )

    await waitFor(() => {
      expect(result.current.isError).toBe(true)
    })

    expect(result.current.error).toBeTruthy()
  })

  it('does not fetch when profile is empty', () => {
    const { result } = renderHook(
      () => useCostSummary('', '2024-01-01', '2024-01-31'),
      { wrapper: createWrapper() }
    )

    // Should not trigger fetch
    expect(costsApi.getSummary).not.toHaveBeenCalled()
  })

  it('does not fetch when disabled', () => {
    const { result } = renderHook(
      () => useCostSummary('default', '2024-01-01', '2024-01-31', false),
      { wrapper: createWrapper() }
    )

    // Should not trigger fetch
    expect(costsApi.getSummary).not.toHaveBeenCalled()
  })

  it('refetches when parameters change', async () => {
    const mockData1 = { total_cost: 1000 }
    const mockData2 = { total_cost: 1500 }

    vi.mocked(costsApi.getSummary)
      .mockResolvedValueOnce(mockData1)
      .mockResolvedValueOnce(mockData2)

    const { result, rerender } = renderHook(
      ({ profileName, startDate, endDate }) => useCostSummary(profileName, startDate, endDate),
      {
        wrapper: createWrapper(),
        initialProps: { profileName: 'default', startDate: '2024-01-01', endDate: '2024-01-31' },
      }
    )

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true)
    })
    expect(result.current.data).toEqual(mockData1)

    // Change dates
    rerender({ profileName: 'default', startDate: '2024-02-01', endDate: '2024-02-28' })

    await waitFor(() => {
      expect(result.current.data).toEqual(mockData2)
    })

    expect(costsApi.getSummary).toHaveBeenCalledTimes(2)
  })

  it('provides refetch function', async () => {
    const mockData = { total_cost: 1000 }
    vi.mocked(costsApi.getSummary).mockResolvedValue(mockData)

    const { result } = renderHook(
      () => useCostSummary('default', '2024-01-01', '2024-01-31'),
      { wrapper: createWrapper() }
    )

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true)
    })

    // Refetch
    await result.current.refetch()

    expect(costsApi.getSummary).toHaveBeenCalledTimes(2)
  })

  it('handles loading state correctly', () => {
    vi.mocked(costsApi.getSummary).mockImplementation(
      () => new Promise(() => {}) // Never resolves
    )

    const { result } = renderHook(
      () => useCostSummary('default', '2024-01-01', '2024-01-31'),
      { wrapper: createWrapper() }
    )

    expect(result.current.isLoading).toBe(true)
    expect(result.current.data).toBeUndefined()
  })
})

describe('useDailyCosts', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('fetches daily costs successfully', async () => {
    const mockData = {
      daily_costs: [
        { date: '2024-01-01', cost: 100 },
        { date: '2024-01-02', cost: 120 },
      ]
    }

    vi.mocked(costsApi.getDailyCosts).mockResolvedValue(mockData)

    const { result } = renderHook(
      () => useDailyCosts('default', '2024-01-01', '2024-01-31'),
      { wrapper: createWrapper() }
    )

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true)
    })

    expect(result.current.data).toEqual(mockData)
    expect(costsApi.getDailyCosts).toHaveBeenCalledWith('default', '2024-01-01', '2024-01-31')
  })
})
