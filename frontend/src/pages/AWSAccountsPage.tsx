import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { awsAccountsApi, AWSAccountCreate, AWSAccount } from '@/api/awsAccounts'
import { Plus, Trash2, Check, X, Eye, EyeOff } from 'lucide-react'
import { SkeletonList } from '@/components/common/LoadingSkeleton'

export function AWSAccountsPage() {
  const [showAddForm, setShowAddForm] = useState(false)
  const [showAccessKey, setShowAccessKey] = useState(false)
  const [showSecretKey, setShowSecretKey] = useState(false)
  const queryClient = useQueryClient()
  const navigate = useNavigate()

  const [formData, setFormData] = useState<AWSAccountCreate>({
    name: '',
    description: '',
    access_key_id: '',
    secret_access_key: '',
    region: 'us-east-1',
  })

  // Fetch AWS accounts
  const { data: accounts, isLoading } = useQuery({
    queryKey: ['awsAccounts'],
    queryFn: () => awsAccountsApi.list(false),
  })

  // Create mutation
  const createMutation = useMutation({
    mutationFn: awsAccountsApi.create,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['awsAccounts'] })
      // Redirect to dashboard after successfully adding account
      navigate('/dashboard')
    },
  })

  // Delete mutation
  const deleteMutation = useMutation({
    mutationFn: awsAccountsApi.delete,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['awsAccounts'] })
    },
  })

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    createMutation.mutate(formData)
  }

  const handleDelete = (accountId: number) => {
    if (confirm('Are you sure you want to delete this AWS account?')) {
      deleteMutation.mutate(accountId)
    }
  }

  return (
    <div className="container mx-auto px-4 py-8">
      <div className="mb-8 flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">AWS Accounts</h1>
          <p className="text-gray-600 mt-2">Manage your AWS account credentials</p>
        </div>
        <button
          onClick={() => setShowAddForm(!showAddForm)}
          className="btn-primary flex items-center gap-2"
        >
          <Plus className="w-4 h-4" />
          Add AWS Account
        </button>
      </div>

      {/* Add Account Form */}
      {showAddForm && (
        <div className="card mb-6">
          <h2 className="text-xl font-semibold text-gray-900 mb-4">Add New AWS Account</h2>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Account Name *
              </label>
              <input
                type="text"
                required
                className="input"
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                placeholder="e.g., Production, Development"
              />
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

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                AWS Access Key ID *
              </label>
              <div className="relative">
                <input
                  type={showAccessKey ? 'text' : 'password'}
                  required
                  className="input pr-10"
                  value={formData.access_key_id}
                  onChange={(e) => setFormData({ ...formData, access_key_id: e.target.value })}
                  placeholder="AKIA..."
                />
                <button
                  type="button"
                  onClick={() => setShowAccessKey(!showAccessKey)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-500 hover:text-gray-700"
                >
                  {showAccessKey ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                AWS Secret Access Key *
              </label>
              <div className="relative">
                <input
                  type={showSecretKey ? 'text' : 'password'}
                  required
                  className="input pr-10"
                  value={formData.secret_access_key}
                  onChange={(e) => setFormData({ ...formData, secret_access_key: e.target.value })}
                  placeholder="Your secret key"
                />
                <button
                  type="button"
                  onClick={() => setShowSecretKey(!showSecretKey)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-500 hover:text-gray-700"
                >
                  {showSecretKey ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Default Region
              </label>
              <select
                className="input"
                value={formData.region}
                onChange={(e) => setFormData({ ...formData, region: e.target.value })}
              >
                <option value="us-east-1">US East (N. Virginia)</option>
                <option value="us-west-2">US West (Oregon)</option>
                <option value="eu-west-1">EU (Ireland)</option>
                <option value="ap-southeast-1">Asia Pacific (Singapore)</option>
              </select>
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
                {createMutation.isPending ? 'Creating...' : 'Create Account'}
              </button>
              <button
                type="button"
                onClick={() => setShowAddForm(false)}
                className="btn-secondary"
              >
                Cancel
              </button>
            </div>
          </form>
        </div>
      )}

      {/* Accounts List */}
      {isLoading ? (
        <SkeletonList count={3} />
      ) : accounts && accounts.length > 0 ? (
        <div className="grid gap-4">
          {accounts.map((account: AWSAccount) => (
            <div key={account.id} className="card">
              <div className="flex justify-between items-start">
                <div className="flex-1">
                  <div className="flex items-center gap-3">
                    <h3 className="text-lg font-semibold text-gray-900">{account.name}</h3>
                    {account.is_active ? (
                      <span className="flex items-center gap-1 px-2 py-1 bg-green-100 text-green-700 text-xs rounded">
                        <Check className="w-3 h-3" /> Active
                      </span>
                    ) : (
                      <span className="flex items-center gap-1 px-2 py-1 bg-gray-100 text-gray-700 text-xs rounded">
                        <X className="w-3 h-3" /> Inactive
                      </span>
                    )}
                  </div>

                  {account.description && (
                    <p className="text-gray-600 mt-1">{account.description}</p>
                  )}

                  <div className="mt-3 grid grid-cols-2 gap-4 text-sm">
                    <div>
                      <span className="text-gray-500">Account ID:</span>
                      <span className="ml-2 font-mono text-gray-900">
                        {account.account_id || 'N/A'}
                      </span>
                    </div>
                    <div>
                      <span className="text-gray-500">Region:</span>
                      <span className="ml-2 text-gray-900">{account.region}</span>
                    </div>
                  </div>

                  {account.validation_error && (
                    <div className="mt-3 p-2 bg-red-50 border border-red-200 rounded text-red-700 text-sm">
                      Validation Error: {account.validation_error}
                    </div>
                  )}

                  {account.last_validated && (
                    <div className="mt-2 text-xs text-gray-500">
                      Last validated: {new Date(account.last_validated).toLocaleString()}
                    </div>
                  )}
                </div>

                <button
                  onClick={() => handleDelete(account.id)}
                  className="p-2 text-red-600 hover:bg-red-50 rounded transition-colors"
                  title="Delete account"
                >
                  <Trash2 className="w-5 h-5" />
                </button>
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="card text-center py-12">
          <p className="text-gray-500">No AWS accounts configured yet.</p>
          <p className="text-gray-400 text-sm mt-2">Click "Add AWS Account" to get started.</p>
        </div>
      )}
    </div>
  )
}
