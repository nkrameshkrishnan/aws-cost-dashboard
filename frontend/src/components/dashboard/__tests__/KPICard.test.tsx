import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { KPICard } from '../KPICard'

describe('KPICard', () => {
  it('renders title and value', () => {
    render(
      <KPICard
        title="Total Cost"
        value="$1,234.56"
      />
    )

    expect(screen.getByText('Total Cost')).toBeInTheDocument()
    expect(screen.getByText('$1,234.56')).toBeInTheDocument()
  })

  it('displays loading state', () => {
    const { container } = render(
      <KPICard
        title="Total Cost"
        value="$0"
        isLoading={true}
      />
    )

    // Should show loading skeleton with animation
    const loadingContainer = container.querySelector('.animate-pulse')
    expect(loadingContainer).toBeInTheDocument()

    // Should have skeleton elements
    const skeletonElements = container.querySelectorAll('.bg-modernGray-200')
    expect(skeletonElements.length).toBe(3)
  })

  it('displays trend when provided - positive (cost decrease)', () => {
    const { container } = render(
      <KPICard
        title="Cost"
        value="$100"
        trend={{ value: 5.2, isPositive: true }}
      />
    )

    // Check that trend value is displayed
    expect(container.textContent).toContain('5.2%')
    // Check for "from last month" text
    expect(container.textContent).toContain('from last month')
  })

  it('displays trend when provided - negative (cost increase)', () => {
    const { container } = render(
      <KPICard
        title="Cost"
        value="$100"
        trend={{ value: -8.5, isPositive: false }}
      />
    )

    // Check that trend value is displayed
    expect(container.textContent).toContain('8.5%')
    // Check for "from last month" text
    expect(container.textContent).toContain('from last month')
  })

  it('displays subtitle when provided', () => {
    render(
      <KPICard
        title="Total Cost"
        value="$1,234.56"
        subtitle="Last 30 days"
      />
    )

    expect(screen.getByText('Last 30 days')).toBeInTheDocument()
  })

  it('renders with custom icon', () => {
    const { container } = render(
      <KPICard
        title="Forecast"
        value="$2,000"
        icon="trending"
      />
    )

    // Icon should be rendered
    expect(container.querySelector('.lucide-trending-up')).toBeInTheDocument()
  })
})
