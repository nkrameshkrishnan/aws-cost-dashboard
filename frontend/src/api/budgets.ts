import api from './axios'

export type BudgetPeriod = 'monthly' | 'quarterly' | 'yearly'

export type BudgetAlertLevel = 'normal' | 'warning' | 'critical' | 'exceeded'

export interface BudgetCreate {
  name: string
  description?: string
  aws_account_id: number
  amount: number
  period?: BudgetPeriod
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
  days_remaining?: number
  alert_level: BudgetAlertLevel
  threshold_warning: number
  threshold_critical: number
  projected_spend?: number
  projected_percentage?: number
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

export const budgetsApi = {
  /**
   * Create a new budget
   */
  create: async (data: BudgetCreate): Promise<Budget> => {
    const response = await api.post('/budgets/', data)
    return response.data
  },

  /**
   * List all budgets
   */
  list: async (awsAccountId?: number, activeOnly: boolean = true): Promise<Budget[]> => {
    const params: any = { active_only: activeOnly }
    if (awsAccountId) {
      params.aws_account_id = awsAccountId
    }
    const response = await api.get('/budgets/', { params })
    return response.data
  },

  /**
   * Get budget summary
   */
  summary: async (awsAccountId?: number): Promise<BudgetSummary> => {
    const params: any = {}
    if (awsAccountId) {
      params.aws_account_id = awsAccountId
    }
    const response = await api.get('/budgets/summary', { params })
    return response.data
  },

  /**
   * Get a specific budget
   */
  get: async (budgetId: number): Promise<Budget> => {
    const response = await api.get(`/budgets/${budgetId}`)
    return response.data
  },

  /**
   * Get budget status with current spending
   */
  status: async (budgetId: number): Promise<BudgetStatus> => {
    const response = await api.get(`/budgets/${budgetId}/status`)
    return response.data
  },

  /**
   * Update a budget
   */
  update: async (budgetId: number, data: BudgetUpdate): Promise<Budget> => {
    const response = await api.put(`/budgets/${budgetId}`, data)
    return response.data
  },

  /**
   * Delete a budget
   */
  delete: async (budgetId: number): Promise<void> => {
    await api.delete(`/budgets/${budgetId}`)
  },

  /**
   * Sync budgets from AWS Budgets API
   */
  syncFromAWS: async (accountName: string, overwrite: boolean = false): Promise<{
    total_found: number
    imported: number
    updated: number
    skipped: number
    errors: string[]
  }> => {
    const response = await api.post('/budgets/sync-from-aws', null, {
      params: { account_name: accountName, overwrite }
    })
    return response.data
  },

  /**
   * Get budgets from AWS without importing
   */
  getFromAWS: async (accountName: string): Promise<{
    account_name: string
    budgets_count: number
    budgets: any[]
  }> => {
    const response = await api.get(`/budgets/from-aws/${accountName}`)
    return response.data
  },
}
