/**
 * Budget-related TypeScript types
 */

export type BudgetPeriod = 'monthly' | 'quarterly' | 'yearly'

export type BudgetAlertLevel = 'normal' | 'warning' | 'critical' | 'exceeded'

export interface Budget {
  id: number
  name: string
  description?: string
  aws_account_id: number
  amount: number
  period: BudgetPeriod
  start_date: string
  end_date?: string
  threshold_warning: number
  threshold_critical: number
  is_active: boolean
  created_at: string
  updated_at?: string
}

export interface BudgetCreate {
  name: string
  description?: string
  aws_account_id: number
  amount: number
  period: BudgetPeriod
  start_date: string
  end_date?: string
  threshold_warning?: number
  threshold_critical?: number
  is_active?: boolean
}

export interface BudgetUpdate {
  name?: string
  description?: string
  amount?: number
  period?: BudgetPeriod
  start_date?: string
  end_date?: string
  threshold_warning?: number
  threshold_critical?: number
  is_active?: boolean
}

export interface BudgetStatus {
  budget_id: number
  budget_name: string
  budget_amount: number
  period: BudgetPeriod
  start_date: string
  end_date?: string
  current_spend: number
  percentage_used: number
  remaining: number
  days_remaining: number | null
  alert_level: BudgetAlertLevel
  threshold_warning: number
  threshold_critical: number
  projected_spend?: number | null
  projected_percentage?: number | null
  is_projected_to_exceed: boolean
}

export interface BudgetSummary {
  total_budgets: number
  active_budgets: number
  total_budget_amount: number
  total_current_spend: number
  budgets_at_warning: number
  budgets_at_critical: number
  budgets_exceeded: number
}
