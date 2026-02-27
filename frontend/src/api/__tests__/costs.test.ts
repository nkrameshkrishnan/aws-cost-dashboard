import { describe, it, expect, vi, beforeEach } from 'vitest'
import { costsApi } from '../costs'
import api from '../axios'

// Mock the axios instance
vi.mock('../axios')

describe('Costs API', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  describe('getSummary', () => {
    it('fetches cost summary successfully', async () => {
      const mockResponse = {
        data: {
          total_cost: 1000,
          period: 'monthly',
          currency: 'USD',
        },
      }

      vi.mocked(api.get).mockResolvedValue(mockResponse)

      const result = await costsApi.getSummary('default', '2024-01-01', '2024-01-31')

      expect(result).toEqual(mockResponse.data)
      expect(api.get).toHaveBeenCalledWith('/costs/summary', {
        params: {
          profile_name: 'default',
          start_date: '2024-01-01',
          end_date: '2024-01-31',
        },
      })
    })

    it('handles API errors', async () => {
      vi.mocked(api.get).mockRejectedValue(new Error('API Error'))

      await expect(
        costsApi.getSummary('default', '2024-01-01', '2024-01-31')
      ).rejects.toThrow('API Error')
    })

    it('sends correct query parameters', async () => {
      const mockResponse = { data: { total_cost: 500 } }
      vi.mocked(api.get).mockResolvedValue(mockResponse)

      await costsApi.getSummary('production', '2024-02-01', '2024-02-28')

      expect(api.get).toHaveBeenCalledWith('/costs/summary', {
        params: {
          profile_name: 'production',
          start_date: '2024-02-01',
          end_date: '2024-02-28',
        },
      })
    })
  })

  describe('getDailyCosts', () => {
    it('fetches daily costs successfully', async () => {
      const mockResponse = {
        data: {
          daily_costs: [
            { date: '2024-01-01', cost: 100 },
            { date: '2024-01-02', cost: 150 },
          ],
        },
      }

      vi.mocked(api.get).mockResolvedValue(mockResponse)

      const result = await costsApi.getDailyCosts('default', '2024-01-01', '2024-01-31')

      expect(result).toEqual(mockResponse.data)
      expect(api.get).toHaveBeenCalledWith('/costs/daily', {
        params: {
          profile_name: 'default',
          start_date: '2024-01-01',
          end_date: '2024-01-31',
        },
      })
    })

    it('handles network errors', async () => {
      vi.mocked(api.get).mockRejectedValue(new Error('Network error'))

      await expect(
        costsApi.getDailyCosts('default', '2024-01-01', '2024-01-31')
      ).rejects.toThrow('Network error')
    })
  })

  describe('getServiceBreakdown', () => {
    it('fetches costs by service successfully', async () => {
      const mockResponse = {
        data: {
          services: [
            { service: 'Amazon EC2', cost: 500 },
            { service: 'Amazon RDS', cost: 300 },
          ],
        },
      }

      vi.mocked(api.get).mockResolvedValue(mockResponse)

      const result = await costsApi.getServiceBreakdown('default', '2024-01-01', '2024-01-31')

      expect(result).toEqual(mockResponse.data)
      expect(api.get).toHaveBeenCalledWith('/costs/by-service', {
        params: {
          profile_name: 'default',
          start_date: '2024-01-01',
          end_date: '2024-01-31',
          top_n: 10,
        },
      })
    })

    it('handles empty response', async () => {
      const mockResponse = { data: { services: [] } }
      vi.mocked(api.get).mockResolvedValue(mockResponse)

      const result = await costsApi.getServiceBreakdown('default', '2024-01-01', '2024-01-31')

      expect(result).toEqual(mockResponse.data)
    })

    it('supports custom topN parameter', async () => {
      const mockResponse = { data: { services: [] } }
      vi.mocked(api.get).mockResolvedValue(mockResponse)

      await costsApi.getServiceBreakdown('default', '2024-01-01', '2024-01-31', 5)

      expect(api.get).toHaveBeenCalledWith('/costs/by-service', {
        params: {
          profile_name: 'default',
          start_date: '2024-01-01',
          end_date: '2024-01-31',
          top_n: 5,
        },
      })
    })
  })

  describe('getForecast', () => {
    it('fetches cost forecast successfully', async () => {
      const mockResponse = {
        data: {
          forecast_amount: 3000,
          confidence_level: 0.95,
          forecast_dates: [
            { date: '2024-02-01', amount: 1000 },
            { date: '2024-02-02', amount: 1100 },
          ],
        },
      }

      vi.mocked(api.get).mockResolvedValue(mockResponse)

      const result = await costsApi.getForecast('default', 30)

      expect(result).toEqual(mockResponse.data)
      expect(api.get).toHaveBeenCalledWith('/costs/forecast', {
        params: {
          profile_name: 'default',
          days: 30,
          granularity: 'MONTHLY',
        },
      })
    })

    it('handles forecast unavailable', async () => {
      vi.mocked(api.get).mockRejectedValue({
        response: { status: 404, data: { message: 'Forecast not available' } },
      })

      await expect(costsApi.getForecast('default', 30)).rejects.toThrow()
    })

    it('supports custom granularity parameter', async () => {
      const mockResponse = { data: { forecast_amount: 1000 } }
      vi.mocked(api.get).mockResolvedValue(mockResponse)

      await costsApi.getForecast('default', 7, 'DAILY')

      expect(api.get).toHaveBeenCalledWith('/costs/forecast', {
        params: {
          profile_name: 'default',
          days: 7,
          granularity: 'DAILY',
        },
      })
    })
  })

  describe('Error handling', () => {
    it('handles 401 unauthorized', async () => {
      vi.mocked(api.get).mockRejectedValue({
        response: { status: 401, data: { message: 'Unauthorized' } },
      })

      await expect(
        costsApi.getSummary('default', '2024-01-01', '2024-01-31')
      ).rejects.toThrow()
    })

    it('handles 500 server error', async () => {
      vi.mocked(api.get).mockRejectedValue({
        response: { status: 500, data: { message: 'Internal server error' } },
      })

      await expect(
        costsApi.getSummary('default', '2024-01-01', '2024-01-31')
      ).rejects.toThrow()
    })

    it('handles network timeout', async () => {
      vi.mocked(api.get).mockRejectedValue({
        code: 'ECONNABORTED',
        message: 'timeout of 5000ms exceeded',
      })

      await expect(
        costsApi.getSummary('default', '2024-01-01', '2024-01-31')
      ).rejects.toThrow()
    })
  })

  describe('Request parameters', () => {
    it('transforms camelCase to snake_case for API params', async () => {
      const mockResponse = { data: {} }
      vi.mocked(api.get).mockResolvedValue(mockResponse)

      await costsApi.getSummary('staging', '2024-01-01', '2024-01-31')

      expect(api.get).toHaveBeenCalledWith('/costs/summary', {
        params: expect.objectContaining({
          profile_name: 'staging',
          start_date: '2024-01-01',
          end_date: '2024-01-31',
        }),
      })
    })

    it('handles different profile names', async () => {
      const mockResponse = { data: { total_cost: 0 } }
      vi.mocked(api.get).mockResolvedValue(mockResponse)

      await costsApi.getSummary('production', '2024-01-01', '2024-01-31')

      const callParams = vi.mocked(api.get).mock.calls[0][1]?.params
      expect(callParams?.profile_name).toBe('production')
    })
  })
})
