import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { ServiceBreakdownPie } from '../ServiceBreakdownPie'
import * as useCostDataModule from '@/hooks/useCostData'

// Mock the hooks
vi.mock('@/hooks/useCostData')

// Mock DrillDownModal component
vi.mock('@/components/common/DrillDownModal', () => ({
  DrillDownModal: () => <div data-testid="drill-down-modal">Drill Down Modal</div>,
}))

// Mock Recharts
vi.mock('recharts', () => ({
  PieChart: ({ children }: any) => <div data-testid="pie-chart">{children}</div>,
  Pie: ({ data, dataKey }: any) => (
    <div data-testid="pie" data-items={data?.length} data-key={dataKey} />
  ),
  Cell: ({ fill }: any) => <div data-testid="cell" style={{ fill }} />,
  Tooltip: () => <div data-testid="tooltip" />,
  Legend: () => <div data-testid="legend" />,
  ResponsiveContainer: ({ children }: any) => (
    <div data-testid="responsive-container">{children}</div>
  ),
}))

describe('ServiceBreakdownPie', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  const mockServiceData = {
    services: [
      { service: 'Amazon EC2', cost: 500 },
      { service: 'Amazon RDS', cost: 300 },
      { service: 'Amazon S3', cost: 200 },
    ],
    total_cost: 1000,
  }

  it('renders pie chart with data', () => {
    vi.mocked(useCostDataModule.useServiceBreakdown).mockReturnValue({
      data: mockServiceData,
      isLoading: false,
      error: null,
      refetch: vi.fn(),
      isError: false,
      isSuccess: true,
    } as any)

    render(
      <ServiceBreakdownPie
        profileName="default"
        startDate="2024-01-01"
        endDate="2024-01-31"
      />
    )

    expect(screen.getByTestId('responsive-container')).toBeInTheDocument()
    expect(screen.getByTestId('pie-chart')).toBeInTheDocument()
    expect(screen.getByTestId('pie')).toBeInTheDocument()
  })

  it('shows loading state', () => {
    vi.mocked(useCostDataModule.useServiceBreakdown).mockReturnValue({
      data: undefined,
      isLoading: true,
      error: null,
      refetch: vi.fn(),
      isError: false,
      isSuccess: false,
    } as any)

    render(
      <ServiceBreakdownPie
        profileName="default"
        startDate="2024-01-01"
        endDate="2024-01-31"
      />
    )

    expect(screen.getByText(/loading service data/i)).toBeInTheDocument()
  })

  it('handles empty data', () => {
    vi.mocked(useCostDataModule.useServiceBreakdown).mockReturnValue({
      data: { services: [], total_cost: 0 },
      isLoading: false,
      error: null,
      refetch: vi.fn(),
      isError: false,
      isSuccess: true,
    } as any)

    render(
      <ServiceBreakdownPie
        profileName="default"
        startDate="2024-01-01"
        endDate="2024-01-31"
      />
    )

    expect(screen.getByText(/no service cost data available/i)).toBeInTheDocument()
  })

  it('renders legend', () => {
    vi.mocked(useCostDataModule.useServiceBreakdown).mockReturnValue({
      data: mockServiceData,
      isLoading: false,
      error: null,
      refetch: vi.fn(),
      isError: false,
      isSuccess: true,
    } as any)

    render(
      <ServiceBreakdownPie
        profileName="default"
        startDate="2024-01-01"
        endDate="2024-01-31"
      />
    )

    expect(screen.getByTestId('legend')).toBeInTheDocument()
  })

  it('renders tooltip', () => {
    vi.mocked(useCostDataModule.useServiceBreakdown).mockReturnValue({
      data: mockServiceData,
      isLoading: false,
      error: null,
      refetch: vi.fn(),
      isError: false,
      isSuccess: true,
    } as any)

    render(
      <ServiceBreakdownPie
        profileName="default"
        startDate="2024-01-01"
        endDate="2024-01-31"
      />
    )

    expect(screen.getByTestId('tooltip')).toBeInTheDocument()
  })

  it('displays all service entries', () => {
    vi.mocked(useCostDataModule.useServiceBreakdown).mockReturnValue({
      data: mockServiceData,
      isLoading: false,
      error: null,
      refetch: vi.fn(),
      isError: false,
      isSuccess: true,
    } as any)

    render(
      <ServiceBreakdownPie
        profileName="default"
        startDate="2024-01-01"
        endDate="2024-01-31"
      />
    )

    const pieElement = screen.getByTestId('pie')
    expect(pieElement).toHaveAttribute('data-items', '3')
  })

  it('handles single service', () => {
    vi.mocked(useCostDataModule.useServiceBreakdown).mockReturnValue({
      data: {
        services: [{ service: 'Amazon EC2', cost: 1000 }],
        total_cost: 1000,
      },
      isLoading: false,
      error: null,
      refetch: vi.fn(),
      isError: false,
      isSuccess: true,
    } as any)

    render(
      <ServiceBreakdownPie
        profileName="default"
        startDate="2024-01-01"
        endDate="2024-01-31"
      />
    )

    expect(screen.getByTestId('pie-chart')).toBeInTheDocument()
  })

  it('handles large number of services', () => {
    const manyServices = {
      services: Array.from({ length: 20 }, (_, i) => ({
        service: `Service ${i}`,
        cost: 100,
      })),
      total_cost: 2000,
    }

    vi.mocked(useCostDataModule.useServiceBreakdown).mockReturnValue({
      data: manyServices,
      isLoading: false,
      error: null,
      refetch: vi.fn(),
      isError: false,
      isSuccess: true,
    } as any)

    render(
      <ServiceBreakdownPie
        profileName="default"
        startDate="2024-01-01"
        endDate="2024-01-31"
      />
    )

    expect(screen.getByTestId('pie-chart')).toBeInTheDocument()
  })
})
