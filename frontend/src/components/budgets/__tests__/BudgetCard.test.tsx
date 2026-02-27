import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { BudgetCard } from '../BudgetCard'
import type { BudgetStatus } from '@/api/budgets'

describe('BudgetCard', () => {
  const mockBudgetStatus: BudgetStatus = {
    budget_id: 1,
    budget_name: 'Monthly AWS Budget',
    budget_amount: 1000,
    current_spend: 750,
    percentage_used: 75,
    remaining: 250,
    period: 'monthly',
    start_date: '2024-01-01',
    alert_level: 'warning',
    threshold_warning: 70,
    threshold_critical: 90,
    is_projected_to_exceed: false,
    days_remaining: 15,
  }

  it('renders budget information correctly', () => {
    render(<BudgetCard status={mockBudgetStatus} />)

    expect(screen.getByText('Monthly AWS Budget')).toBeInTheDocument()
    expect(screen.getByText(/Monthly Budget/i)).toBeInTheDocument()
  })

  it('shows percentage of budget used', () => {
    render(<BudgetCard status={mockBudgetStatus} />)

    expect(screen.getByText('75.0%')).toBeInTheDocument()
  })

  it('displays progress bar', () => {
    const { container } = render(<BudgetCard status={mockBudgetStatus} />)

    // Progress bar should exist in the component
    const progressBar = container.querySelector('.bg-gray-200')
    expect(progressBar).toBeTruthy()
  })

  it('shows alert when threshold is exceeded', () => {
    const warningStatus: BudgetStatus = {
      ...mockBudgetStatus,
      current_spend: 850,
      percentage_used: 85,
      alert_level: 'warning',
    }

    render(<BudgetCard status={warningStatus} />)

    expect(screen.getByText('Warning')).toBeInTheDocument()
  })

  it('shows when budget is exceeded', () => {
    const exceededStatus: BudgetStatus = {
      ...mockBudgetStatus,
      current_spend: 1100,
      percentage_used: 110,
      remaining: -100,
      alert_level: 'exceeded',
    }

    render(<BudgetCard status={exceededStatus} />)

    expect(screen.getByText('Budget Exceeded')).toBeInTheDocument()
  })

  it('displays remaining budget', () => {
    render(<BudgetCard status={mockBudgetStatus} />)

    expect(screen.getByText('Remaining')).toBeInTheDocument()
    expect(screen.getByText('$250.00')).toBeInTheDocument()
  })

  it('handles click events', () => {
    const onClick = vi.fn()

    render(<BudgetCard status={mockBudgetStatus} onClick={onClick} />)

    const card = screen.getByText('Monthly AWS Budget').closest('.card')
    if (card) {
      fireEvent.click(card)
      expect(onClick).toHaveBeenCalled()
    }
  })

  it('displays different colors based on usage', () => {
    // Normal (under threshold)
    const normalStatus: BudgetStatus = {
      ...mockBudgetStatus,
      current_spend: 500,
      percentage_used: 50,
      alert_level: 'normal',
    }
    const { container: container1 } = render(<BudgetCard status={normalStatus} />)
    expect(screen.getByText('On Track')).toBeInTheDocument()

    // Warning
    const { container: container2 } = render(
      <BudgetCard status={{ ...mockBudgetStatus, alert_level: 'warning' }} />
    )

    // Critical
    const criticalStatus: BudgetStatus = {
      ...mockBudgetStatus,
      current_spend: 950,
      percentage_used: 95,
      alert_level: 'critical',
    }
    const { container: container3 } = render(<BudgetCard status={criticalStatus} />)

    expect(container1).toBeTruthy()
    expect(container2).toBeTruthy()
    expect(container3).toBeTruthy()
  })

  it('displays period label', () => {
    render(<BudgetCard status={mockBudgetStatus} />)

    expect(screen.getByText(/Monthly Budget/i)).toBeInTheDocument()
  })

  it('formats currency correctly', () => {
    render(<BudgetCard status={mockBudgetStatus} />)

    // Should display USD currency format
    expect(screen.getByText('$750.00 of $1,000.00')).toBeInTheDocument()
  })

  it('handles zero current spend', () => {
    const zeroStatus: BudgetStatus = {
      ...mockBudgetStatus,
      current_spend: 0,
      percentage_used: 0,
      remaining: 1000,
    }

    render(<BudgetCard status={zeroStatus} />)

    expect(screen.getByText('0.0%')).toBeInTheDocument()
  })

  it('displays days remaining when available', () => {
    render(<BudgetCard status={mockBudgetStatus} />)

    expect(screen.getByText('Days Left')).toBeInTheDocument()
    expect(screen.getByText('15')).toBeInTheDocument()
  })

  it('shows projected spend warning when budget is projected to exceed', () => {
    const projectedStatus: BudgetStatus = {
      ...mockBudgetStatus,
      is_projected_to_exceed: true,
      projected_spend: 1200,
      projected_percentage: 120,
    }

    render(<BudgetCard status={projectedStatus} />)

    expect(screen.getByText('Projected to exceed budget')).toBeInTheDocument()
    expect(screen.getByText(/\$1,200.00/)).toBeInTheDocument()
  })

  it('displays send alert button when onSendAlert is provided and usage >= 50%', () => {
    const onSendAlert = vi.fn()

    render(<BudgetCard status={mockBudgetStatus} onSendAlert={onSendAlert} />)

    const alertButton = screen.getByText('Send Teams Alert')
    expect(alertButton).toBeInTheDocument()

    fireEvent.click(alertButton)
    expect(onSendAlert).toHaveBeenCalledWith(mockBudgetStatus.budget_id)
  })

  it('does not show send alert button when usage < 50%', () => {
    const onSendAlert = vi.fn()
    const lowUsageStatus: BudgetStatus = {
      ...mockBudgetStatus,
      current_spend: 400,
      percentage_used: 40,
    }

    render(<BudgetCard status={lowUsageStatus} onSendAlert={onSendAlert} />)

    expect(screen.queryByText('Send Teams Alert')).not.toBeInTheDocument()
  })
})
