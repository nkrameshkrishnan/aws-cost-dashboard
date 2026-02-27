import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { CostTrendChart } from '../CostTrendChart'
import * as useCostDataModule from '@/hooks/useCostData'

// Mock Recharts components
vi.mock('recharts', () => ({
  ComposedChart: ({ children }: any) => <div data-testid="composed-chart">{children}</div>,
  LineChart: ({ children }: any) => <div data-testid="line-chart">{children}</div>,
  Line: ({ dataKey }: any) => <div data-testid={`line-${dataKey}`} />,
  Area: ({ dataKey }: any) => <div data-testid={`area-${dataKey}`} />,
  XAxis: ({ dataKey }: any) => <div data-testid={`xaxis-${dataKey}`} />,
  YAxis: () => <div data-testid="yaxis" />,
  CartesianGrid: () => <div data-testid="grid" />,
  Tooltip: () => <div data-testid="tooltip" />,
  Legend: () => <div data-testid="legend" />,
  ResponsiveContainer: ({ children }: any) => <div data-testid="responsive-container">{children}</div>,
}))

// Mock date-fns
vi.mock('date-fns', () => ({
  format: (date: any, formatStr: string) => {
    if (formatStr === 'MMM dd') return 'Jan 01'
    return '2024-01-01'
  },
  parseISO: (date: string) => new Date(date),
}))

// Mock the useDailyCosts hook
vi.mock('@/hooks/useCostData')

describe('CostTrendChart', () => {
  const mockData = {
    daily_costs: [
      { date: '2024-01-01', cost: 100 },
      { date: '2024-01-02', cost: 120 },
      { date: '2024-01-03', cost: 110 },
      { date: '2024-01-04', cost: 150 },
    ]
  }

  const defaultProps = {
    profileName: 'default',
    startDate: '2024-01-01',
    endDate: '2024-01-31',
  }

  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders chart with data', () => {
    vi.mocked(useCostDataModule.useDailyCosts).mockReturnValue({
      data: mockData,
      isLoading: false,
      error: null,
      refetch: vi.fn(),
      isError: false,
      isSuccess: true,
    } as any)

    render(<CostTrendChart {...defaultProps} />)

    expect(screen.getByTestId('responsive-container')).toBeInTheDocument()
    expect(screen.getByTestId('composed-chart')).toBeInTheDocument()
  })

  it('shows loading state when loading', () => {
    vi.mocked(useCostDataModule.useDailyCosts).mockReturnValue({
      data: undefined,
      isLoading: true,
      error: null,
      refetch: vi.fn(),
      isError: false,
      isSuccess: false,
    } as any)

    render(<CostTrendChart {...defaultProps} />)

    expect(screen.getByText(/loading cost data/i)).toBeInTheDocument()
  })

  it('shows error state when error occurs', () => {
    vi.mocked(useCostDataModule.useDailyCosts).mockReturnValue({
      data: undefined,
      isLoading: false,
      error: new Error('Failed to load data'),
      refetch: vi.fn(),
      isError: true,
      isSuccess: false,
    } as any)

    render(<CostTrendChart {...defaultProps} />)

    expect(screen.getByText(/error loading cost data/i)).toBeInTheDocument()
  })

  it('shows empty state when no data', () => {
    vi.mocked(useCostDataModule.useDailyCosts).mockReturnValue({
      data: { daily_costs: [] },
      isLoading: false,
      error: null,
      refetch: vi.fn(),
      isError: false,
      isSuccess: true,
    } as any)

    render(<CostTrendChart {...defaultProps} />)

    expect(screen.getByText(/no cost data available/i)).toBeInTheDocument()
  })

  it('renders all chart components', () => {
    vi.mocked(useCostDataModule.useDailyCosts).mockReturnValue({
      data: mockData,
      isLoading: false,
      error: null,
      refetch: vi.fn(),
      isError: false,
      isSuccess: true,
    } as any)

    render(<CostTrendChart {...defaultProps} />)

    expect(screen.getByTestId('composed-chart')).toBeInTheDocument()
    expect(screen.getByTestId('grid')).toBeInTheDocument()
    expect(screen.getByTestId('tooltip')).toBeInTheDocument()
    expect(screen.getByTestId('legend')).toBeInTheDocument()
  })

  it('handles empty data object gracefully', () => {
    vi.mocked(useCostDataModule.useDailyCosts).mockReturnValue({
      data: undefined,
      isLoading: false,
      error: null,
      refetch: vi.fn(),
      isError: false,
      isSuccess: true,
    } as any)

    render(<CostTrendChart {...defaultProps} />)

    // Should show empty state message
    expect(screen.getByText(/no cost data available/i)).toBeInTheDocument()
  })

  it('renders Line and Area components for cost data', () => {
    vi.mocked(useCostDataModule.useDailyCosts).mockReturnValue({
      data: mockData,
      isLoading: false,
      error: null,
      refetch: vi.fn(),
      isError: false,
      isSuccess: true,
    } as any)

    render(<CostTrendChart {...defaultProps} />)

    expect(screen.getByTestId('line-cost')).toBeInTheDocument()
    expect(screen.getByTestId('area-cost')).toBeInTheDocument()
  })
})
