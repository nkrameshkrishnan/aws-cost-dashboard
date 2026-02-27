import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { budgetsApi, type BudgetCreate, type BudgetStatus } from '@/api/budgets'
import { awsAccountsApi } from '@/api/awsAccounts'
import { teamsApi } from '@/api/teams'
import { Plus, Trash2, DollarSign, RefreshCw, Bell, Cloud, AlertCircle } from 'lucide-react'
import { BudgetCard } from '@/components/budgets/BudgetCard'
import { LoadingSpinner } from '@/components/common/LoadingSpinner'

export function BudgetManagement() {
  const [showAddForm, setShowAddForm] = useState(false)
  const [selectedAccountForSync, setSelectedAccountForSync] = useState('')
  const [syncMessage, setSyncMessage] = useState('')
  const [alertMessage, setAlertMessage] = useState('')
  const queryClient = useQueryClient()
  const navigate = useNavigate()

  const [formData, setFormData] = useState<BudgetCreate>({
    name: '',
    description: '',
    aws_account_id: 0,
    amount: 1000,
    period: 'monthly',
    start_date: new Date().toISOString().split('T')[0],
    threshold_warning: 80,
    threshold_critical: 100,
    is_active: true
  })

  // Fetch AWS accounts for the dropdown
  const { data: accounts, isLoading: loadingAccounts } = useQuery({
    queryKey: ['awsAccounts'],
    queryFn: () => awsAccountsApi.list(true),
    retry: 1
  })

  const hasAccounts = accounts && accounts.length > 0

  // Fetch budgets
  const { data: budgets, isLoading } = useQuery({
    queryKey: ['budgets'],
    queryFn: () => budgetsApi.list()
  })

  // Fetch budget statuses
  const { data: budgetStatuses } = useQuery({
    queryKey: ['budgetStatuses', budgets],
    queryFn: async () => {
      if (!budgets || budgets.length === 0) return []
      const statuses = await Promise.all(
        budgets.map(b => budgetsApi.status(b.id))
      )
      return statuses
    },
    enabled: !!budgets && budgets.length > 0
  })

  // Fetch summary
  const { data: summary } = useQuery({
    queryKey: ['budgetSummary'],
    queryFn: () => budgetsApi.summary()
  })

  // Create mutation
  const createMutation = useMutation({
    mutationFn: budgetsApi.create,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['budgets'] })
      queryClient.invalidateQueries({ queryKey: ['budgetSummary'] })
      setShowAddForm(false)
      resetForm()
    }
  })

  // Delete mutation
  const deleteMutation = useMutation({
    mutationFn: budgetsApi.delete,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['budgets'] })
      queryClient.invalidateQueries({ queryKey: ['budgetSummary'] })
    }
  })

  // Sync from AWS mutation
  const syncMutation = useMutation({
    mutationFn: ({ accountName, overwrite }: { accountName: string; overwrite: boolean }) =>
      budgetsApi.syncFromAWS(accountName, overwrite),
    onSuccess: (result) => {
      queryClient.invalidateQueries({ queryKey: ['budgets'] })
      queryClient.invalidateQueries({ queryKey: ['budgetSummary'] })
      setSyncMessage(
        `Sync complete! Found: ${result.total_found}, Imported: ${result.imported}, Updated: ${result.updated}, Skipped: ${result.skipped}${
          result.errors.length > 0 ? `, Errors: ${result.errors.length}` : ''
        }`
      )
      setTimeout(() => setSyncMessage(''), 10000)
    },
    onError: (error: any) => {
      setSyncMessage(`Sync failed: ${error.response?.data?.detail || error.message}`)
      setTimeout(() => setSyncMessage(''), 10000)
    }
  })

  // Send budget alert mutation
  const sendAlertMutation = useMutation({
    mutationFn: (budgetId: number) => teamsApi.sendBudgetAlert(budgetId),
    onSuccess: (result) => {
      setAlertMessage(
        `✅ ${result.message}${
          result.errors.length > 0 ? ` (${result.errors.length} errors)` : ''
        }`
      )
      setTimeout(() => setAlertMessage(''), 8000)
    },
    onError: (error: any) => {
      setAlertMessage(`❌ Failed to send alert: ${error.response?.data?.detail || error.message}`)
      setTimeout(() => setAlertMessage(''), 8000)
    }
  })

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    createMutation.mutate(formData)
  }

  const handleDelete = (budgetId: number, budgetName: string) => {
    if (confirm(`Are you sure you want to delete budget "${budgetName}"?`)) {
      deleteMutation.mutate(budgetId)
    }
  }

  const handleSyncFromAWS = () => {
    if (!selectedAccountForSync) {
      setSyncMessage('Please select an AWS account first')
      setTimeout(() => setSyncMessage(''), 3000)
      return
    }

    const overwrite = confirm(
      'Do you want to overwrite existing budgets with the same name?\n\nClick OK to overwrite, Cancel to skip duplicates.'
    )

    syncMutation.mutate({ accountName: selectedAccountForSync, overwrite })
  }

  const handleSendAlert = (budgetId: number) => {
    const budget = budgetStatuses?.find(b => b.budget_id === budgetId)
    if (!budget) return

    if (confirm(
      `Send Teams alert for budget "${budget.budget_name}"?\n\n` +
      `Current spend: $${budget.current_spend.toFixed(2)} (${budget.percentage_used.toFixed(1)}%)\n` +
      `This will notify all active Teams webhooks configured for budget alerts.`
    )) {
      sendAlertMutation.mutate(budgetId)
    }
  }

  const resetForm = () => {
    setFormData({
      name: '',
      description: '',
      aws_account_id: 0,
      amount: 1000,
      period: 'monthly',
      start_date: new Date().toISOString().split('T')[0],
      threshold_warning: 80,
      threshold_critical: 100,
      is_active: true
    })
  }

  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 0
    }).format(amount)
  }

  return (
    <div className="container mx-auto px-4 py-8">
      <div className="mb-8 flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">Budget Management</h1>
          <p className="text-gray-600 mt-2">Track and manage your cloud spending budgets</p>
        </div>
        <button
          onClick={() => setShowAddForm(!showAddForm)}
          className="btn-primary flex items-center gap-2"
        >
          <Plus className="w-4 h-4" />
          Create Budget
        </button>
      </div>

      {/* No AWS Accounts Warning */}
      {!loadingAccounts && !hasAccounts && (
        <div className="card mb-8 bg-gradient-to-r from-yellow-50 to-amber-50 border-l-4 border-yellow-500">
          <div className="flex items-start gap-4">
            <div className="p-3 bg-yellow-500 rounded-lg">
              <AlertCircle className="w-6 h-6 text-white" />
            </div>
            <div className="flex-1">
              <h3 className="text-lg font-semibold text-gray-900 mb-2">No AWS Accounts Configured</h3>
              <p className="text-gray-700 mb-4">
                To create and manage budgets, you need to add at least one AWS account first. Budgets help you track spending and get alerts when costs exceed thresholds.
              </p>
              <button
                onClick={() => navigate('/aws-accounts')}
                className="btn-primary flex items-center gap-2"
              >
                <Cloud className="w-4 h-4" />
                Add AWS Account
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Summary Cards */}
      {hasAccounts && summary && (
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-8">
          <div className="card bg-blue-50 border-blue-200">
            <div className="flex items-center gap-3">
              <div className="p-3 bg-blue-100 rounded-lg">
                <DollarSign className="w-6 h-6 text-blue-600" />
              </div>
              <div>
                <p className="text-sm text-gray-600">Total Budget</p>
                <p className="text-2xl font-bold text-gray-900">
                  {formatCurrency(summary.total_budget_amount)}
                </p>
              </div>
            </div>
          </div>

          <div className="card bg-green-50 border-green-200">
            <div className="flex items-center gap-3">
              <div className="p-3 bg-green-100 rounded-lg">
                <DollarSign className="w-6 h-6 text-green-600" />
              </div>
              <div>
                <p className="text-sm text-gray-600">Current Spend</p>
                <p className="text-2xl font-bold text-gray-900">
                  {formatCurrency(summary.total_current_spend)}
                </p>
              </div>
            </div>
          </div>

          <div className="card">
            <p className="text-sm text-gray-600">Active Budgets</p>
            <p className="text-2xl font-bold text-gray-900">{summary.active_budgets}</p>
          </div>

          <div className="card">
            <p className="text-sm text-gray-600">Alerts</p>
            <div className="flex gap-3 mt-2">
              {summary.budgets_exceeded > 0 && (
                <span className="px-2 py-1 bg-red-100 text-red-700 text-xs font-medium rounded">
                  {summary.budgets_exceeded} Exceeded
                </span>
              )}
              {summary.budgets_at_critical > 0 && (
                <span className="px-2 py-1 bg-orange-100 text-orange-700 text-xs font-medium rounded">
                  {summary.budgets_at_critical} Critical
                </span>
              )}
              {summary.budgets_at_warning > 0 && (
                <span className="px-2 py-1 bg-yellow-100 text-yellow-700 text-xs font-medium rounded">
                  {summary.budgets_at_warning} Warning
                </span>
              )}
              {summary.budgets_exceeded === 0 && summary.budgets_at_critical === 0 && summary.budgets_at_warning === 0 && (
                <span className="text-sm text-green-600 font-medium">All on track</span>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Sync from AWS - Optional Feature */}
      {hasAccounts && (
      <div className="card mb-6 bg-gradient-to-r from-blue-50 to-indigo-50 border-blue-200">
        <div className="flex items-start justify-between">
          <div className="flex-1">
            <div className="flex items-center gap-2 mb-2">
              <RefreshCw className="w-5 h-5 text-blue-600" />
              <h3 className="text-lg font-semibold text-gray-900">Import Budgets from AWS</h3>
              <span className="px-2 py-1 bg-yellow-100 text-yellow-800 text-xs font-medium rounded">
                Optional
              </span>
            </div>
            <p className="text-sm text-gray-600 mb-4">
              Sync budgets from AWS Billing and Cost Management console to this dashboard.
            </p>
            <div className="flex items-center gap-3">
              <select
                value={selectedAccountForSync}
                onChange={(e) => setSelectedAccountForSync(e.target.value)}
                className="input max-w-xs"
              >
                <option value="">Select AWS Account</option>
                {accounts?.map((account) => (
                  <option key={account.id} value={account.name}>
                    {account.name}
                  </option>
                ))}
              </select>
              <button
                onClick={handleSyncFromAWS}
                disabled={syncMutation.isPending || !selectedAccountForSync}
                className="btn-primary flex items-center gap-2"
              >
                <RefreshCw className={`w-4 h-4 ${syncMutation.isPending ? 'animate-spin' : ''}`} />
                {syncMutation.isPending ? 'Syncing...' : 'Sync from AWS'}
              </button>
            </div>
            {syncMessage && (
              <div className={`mt-3 p-3 rounded ${
                syncMessage.includes('failed') || syncMessage.includes('Error') || syncMessage.includes('denied')
                  ? 'bg-red-100 text-red-700'
                  : 'bg-green-100 text-green-700'
              }`}>
                {syncMessage}
              </div>
            )}
          </div>
        </div>
      </div>
      )}

      {/* Alert Message Display */}
      {hasAccounts && alertMessage && (
        <div className={`card mb-6 ${
          alertMessage.startsWith('❌')
            ? 'bg-red-50 border-red-200'
            : 'bg-green-50 border-green-200'
        }`}>
          <div className="flex items-center gap-2">
            <Bell className={`w-5 h-5 ${
              alertMessage.startsWith('❌') ? 'text-red-600' : 'text-green-600'
            }`} />
            <p className={`font-medium ${
              alertMessage.startsWith('❌') ? 'text-red-700' : 'text-green-700'
            }`}>
              {alertMessage}
            </p>
          </div>
        </div>
      )}

      {/* Add Budget Form */}
      {hasAccounts && showAddForm && (
        <div className="card mb-6">
          <h2 className="text-xl font-semibold text-gray-900 mb-4">Create New Budget</h2>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Budget Name *
                </label>
                <input
                  type="text"
                  required
                  className="input"
                  value={formData.name}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  placeholder="e.g., Monthly Production Budget"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  AWS Account *
                </label>
                <select
                  required
                  className="input"
                  value={formData.aws_account_id}
                  onChange={(e) => setFormData({ ...formData, aws_account_id: parseInt(e.target.value) })}
                >
                  <option value={0}>Select an account</option>
                  {accounts?.map((account) => (
                    <option key={account.id} value={account.id}>
                      {account.name}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Description
              </label>
              <input
                type="text"
                className="input"
                value={formData.description}
                onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                placeholder="Optional description"
              />
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Budget Amount (USD) *
                </label>
                <input
                  type="number"
                  required
                  min="0"
                  step="0.01"
                  className="input"
                  value={formData.amount}
                  onChange={(e) => setFormData({ ...formData, amount: parseFloat(e.target.value) })}
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Period *
                </label>
                <select
                  className="input"
                  value={formData.period}
                  onChange={(e) => setFormData({ ...formData, period: e.target.value as any })}
                >
                  <option value="monthly">Monthly</option>
                  <option value="quarterly">Quarterly</option>
                  <option value="yearly">Yearly</option>
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Start Date *
                </label>
                <input
                  type="date"
                  required
                  className="input"
                  value={formData.start_date}
                  onChange={(e) => setFormData({ ...formData, start_date: e.target.value })}
                />
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Warning Threshold (%) *
                </label>
                <input
                  type="number"
                  required
                  min="0"
                  max="100"
                  className="input"
                  value={formData.threshold_warning}
                  onChange={(e) => setFormData({ ...formData, threshold_warning: parseFloat(e.target.value) })}
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Critical Threshold (%) *
                </label>
                <input
                  type="number"
                  required
                  min="0"
                  max="200"
                  className="input"
                  value={formData.threshold_critical}
                  onChange={(e) => setFormData({ ...formData, threshold_critical: parseFloat(e.target.value) })}
                />
              </div>
            </div>

            {createMutation.error && (
              <div className="p-3 bg-red-50 border border-red-200 rounded text-red-700 text-sm">
                Error: {String(createMutation.error)}
              </div>
            )}

            <div className="flex gap-3">
              <button
                type="submit"
                disabled={createMutation.isPending}
                className="btn-primary"
              >
                {createMutation.isPending ? 'Creating...' : 'Create Budget'}
              </button>
              <button
                type="button"
                onClick={() => {
                  setShowAddForm(false)
                  resetForm()
                }}
                className="btn-secondary"
              >
                Cancel
              </button>
            </div>
          </form>
        </div>
      )}

      {/* Budgets List */}
      {hasAccounts && (isLoading ? (
        <div className="py-8">
          <LoadingSpinner size="lg" text="Loading budgets..." />
        </div>
      ) : budgetStatuses && budgetStatuses.length > 0 ? (
        <div className="space-y-6">
          <h2 className="text-xl font-semibold text-gray-900">Your Budgets</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {budgetStatuses.map((status) => (
              <div key={status.budget_id} className="relative">
                <BudgetCard
                  status={status}
                  onSendAlert={handleSendAlert}
                />
                <button
                  onClick={() => handleDelete(status.budget_id, status.budget_name)}
                  className="absolute top-3 right-3 p-1.5 text-red-600 bg-white border border-red-200 hover:bg-red-50 rounded shadow-sm transition-colors"
                  title="Delete budget"
                >
                  <Trash2 className="w-4 h-4" />
                </button>
              </div>
            ))}
          </div>
        </div>
      ) : (
        <div className="card text-center py-12">
          <p className="text-gray-500">No budgets configured yet.</p>
          <p className="text-gray-400 text-sm mt-2">Click "Create Budget" to get started.</p>
        </div>
      ))}
    </div>
  )
}
