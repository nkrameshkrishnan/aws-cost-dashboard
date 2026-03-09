/**
 * Settings page for managing application configuration.
 * Includes Microsoft Teams webhook management.
 */
import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { teamsApi } from '@/api/teams'
import type { TeamsWebhook, TeamsWebhookCreate } from '@/types/teams'
import { LoadingSpinner } from '@/components/common/LoadingSpinner'

export default function Settings() {
  const [showCreateModal, setShowCreateModal] = useState(false)
  const [editingWebhook, setEditingWebhook] = useState<TeamsWebhook | null>(null)
  const queryClient = useQueryClient()

  // S3 Configuration State
  const [s3Enabled, setS3Enabled] = useState(() => {
    const saved = localStorage.getItem('s3ExportEnabled')
    return saved === 'true'
  })
  const [s3BucketName, setS3BucketName] = useState(() => {
    return localStorage.getItem('s3ExportBucket') || ''
  })
  const [s3SaveSuccess, setS3SaveSuccess] = useState(false)

  // Fetch webhooks
  const { data: webhooks, isLoading } = useQuery({
    queryKey: ['teams-webhooks'],
    queryFn: () => teamsApi.listWebhooks()
  })

  // Delete webhook mutation
  const deleteMutation = useMutation({
    mutationFn: (id: number) => teamsApi.deleteWebhook(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['teams-webhooks'] })
    }
  })

  // Test webhook mutation
  const testMutation = useMutation({
    mutationFn: (request: { webhook_url: string; webhook_type: 'teams' | 'power_automate' }) =>
      teamsApi.testWebhook(request)
  })

  const handleDelete = async (id: number, name: string) => {
    if (window.confirm(`Are you sure you want to delete webhook "${name}"?`)) {
      await deleteMutation.mutateAsync(id)
    }
  }

  const handleTest = async (webhook: TeamsWebhook) => {
    const result = await testMutation.mutateAsync({
      webhook_url: webhook.webhook_url,
      webhook_type: webhook.webhook_type
    })
    if (result.success) {
      const destination = webhook.webhook_type === 'teams' ? 'Teams channel' : 'Power Automate workflow'
      alert(`✅ Test notification sent! Check your ${destination}.`)
    } else {
      alert('❌ Failed to send test notification. Please check your webhook URL.')
    }
  }

  const handleS3ConfigSave = () => {
    localStorage.setItem('s3ExportEnabled', s3Enabled.toString())
    localStorage.setItem('s3ExportBucket', s3BucketName)
    setS3SaveSuccess(true)
    setTimeout(() => setS3SaveSuccess(false), 3000)
  }

  return (
    <div className="container mx-auto px-4 py-8">
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-modernGray-900 tracking-tight">Settings</h1>
        <p className="text-modernGray-600 mt-2">Manage application configuration and integrations</p>
      </div>

      {/* Microsoft Teams Section */}
      <div className="card mb-6">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h2 className="text-xl font-semibold text-modernGray-900 mb-1">Microsoft Teams Integration</h2>
            <p className="text-sm text-modernGray-600">Configure webhooks to send notifications to Teams channels</p>
          </div>
          <button
            onClick={() => setShowCreateModal(true)}
            className="btn-primary"
          >
            + Add Webhook
          </button>
        </div>

        {isLoading ? (
          <div className="py-8">
            <LoadingSpinner size="md" text="Loading webhooks..." />
          </div>
        ) : webhooks && Array.isArray(webhooks) && webhooks.length > 0 ? (
          <div className="space-y-4">
            {webhooks.map((webhook) => (
              <div
                key={webhook.id}
                className="border border-modernGray-200 rounded-card p-4 hover:border-modernGray-300 transition-colors"
              >
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <h3 className="text-lg font-semibold text-modernGray-900">{webhook.name}</h3>
                    <div className="mt-2 flex items-center gap-2">
                      <span
                        className={`px-2 py-1 text-xs font-medium rounded ${webhook.is_active ? 'bg-modernGreen-100 text-modernGreen-800' : 'bg-modernGray-100 text-modernGray-700'}`}
                      >
                        {webhook.is_active ? 'Active' : 'Inactive'}
                      </span>
                      <span className="px-2 py-1 text-xs font-medium rounded bg-modernTeal-100 text-modernTeal-800">
                        {webhook.webhook_type === 'teams' ? 'Teams' : 'Power Automate'}
                      </span>
                    </div>

                    {webhook.description && (
                      <p className="text-sm text-modernGray-600 mb-3 mt-2">{webhook.description}</p>
                    )}

                    <div className="grid grid-cols-2 gap-4 text-sm mt-2">
                      <span className="font-medium text-modernGray-700">Notifications:</span>
                      <ul className="mt-1 space-y-1 text-modernGray-600">
                        {webhook.send_budget_alerts && <li>• Budget alerts (≥{webhook.budget_threshold_percentage}%)</li>}
                        {webhook.send_cost_summaries && <li>• Cost summaries</li>}
                        {webhook.send_audit_reports && <li>• Audit reports</li>}
                        {!webhook.send_budget_alerts && !webhook.send_cost_summaries && !webhook.send_audit_reports && (
                          <li>• None</li>
                        )}
                      </ul>
                    </div>

                    <div className="mt-3">
                      <span className="font-medium text-modernGray-700">Last sent:</span>
                      <p className="mt-1 text-modernGray-600">
                        {webhook.last_sent_at ? new Date(webhook.last_sent_at).toLocaleString() : 'Never'}
                      </p>
                    </div>
                  </div>

                  <div className="flex gap-2 ml-4">
                    <button
                      onClick={() => handleTest(webhook)}
                      disabled={testMutation.isPending}
                      className="btn-secondary"
                    >
                      Test
                    </button>
                    <button
                      onClick={() => setEditingWebhook(webhook)}
                      className="btn-secondary"
                    >
                      Edit
                    </button>
                    <button
                      onClick={() => handleDelete(webhook.id, webhook.name)}
                      disabled={deleteMutation.isPending}
                      className="px-3 py-1 text-sm border border-modernRed-300 text-modernRed-600 rounded-button hover:bg-modernRed-50 transition-colors disabled:opacity-50"
                    >
                      Delete
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="text-center py-12 bg-modernGray-50 rounded-card">
            <svg className="mx-auto h-12 w-12 text-modernGray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
            </svg>
            <h3 className="mt-2 text-sm font-medium text-modernGray-900">No webhooks configured</h3>
            <p className="mt-1 text-sm text-modernGray-500">Get started by creating a new Teams webhook</p>
            <div className="mt-6">
              <button
                onClick={() => setShowCreateModal(true)}
                className="btn-primary"
              >
                Create Webhook
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Create/Edit Modal */}
      {(showCreateModal || editingWebhook) && (
        <WebhookModal
          webhook={editingWebhook}
          onClose={() => {
            setShowCreateModal(false)
            setEditingWebhook(null)
          }}
          onSuccess={() => {
            setShowCreateModal(false)
            setEditingWebhook(null)
            queryClient.invalidateQueries({ queryKey: ['teams-webhooks'] })
          }}
        />
      )}

      {/* S3 Export Configuration Section */}
      <div className="card mb-6">
        <div className="mb-6">
          <div>
            <h2 className="text-xl font-semibold text-modernGray-900 mb-1">S3 Export Configuration</h2>
            <p className="text-sm text-modernGray-600">
              Configure default S3 bucket for exporting reports (PDF, Excel) across all pages
            </p>
          </div>
        </div>

        <div className="space-y-6">
          {/* Enable/Disable Toggle */}
          <div className="flex items-center justify-between p-4 bg-gray-50 rounded-lg">
            <div className="flex-1">
              <h3 className="text-sm font-semibold text-gray-800 mb-1">Enable S3 Export</h3>
              <p className="text-xs text-gray-600">
                When enabled, export buttons across the dashboard will default to uploading to S3
              </p>
            </div>
            <label className="relative inline-flex items-center cursor-pointer ml-4">
              <input
                type="checkbox"
                checked={s3Enabled}
                onChange={(e) => setS3Enabled(e.target.checked)}
                className="sr-only peer"
                aria-label="Enable S3 Export"
              />
              <div className="w-14 h-7 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-blue-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-6 after:w-6 after:transition-all peer-checked:bg-blue-600"></div>
            </label>
          </div>

          {/* S3 Bucket Name Input */}
          <div className={`transition-opacity ${s3Enabled ? 'opacity-100' : 'opacity-50'}`}>
            <label htmlFor="s3-bucket-name" className="block text-sm font-semibold text-gray-800 mb-2">
              Default S3 Bucket Name
              {s3Enabled && <span className="text-red-500 ml-1">*</span>}
            </label>
            <input
              type="text"
              id="s3-bucket-name"
              value={s3BucketName}
              onChange={(e) => setS3BucketName(e.target.value)}
              disabled={!s3Enabled}
              placeholder="my-aws-reports-bucket"
              className="w-full px-4 py-3 border-2 border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent text-gray-800 placeholder-gray-400 disabled:bg-gray-100 disabled:cursor-not-allowed"
            />
            <p className="mt-2 text-xs text-gray-600">
              <span className="font-semibold">💡 Requirements:</span>
              <br />
              • Your AWS credentials must have <code className="bg-gray-100 px-1 rounded">s3:PutObject</code> permission
              <br />
              • Bucket must exist in the same AWS account as your configured profile
              <br />
              • Reports will be uploaded to the root of this bucket with timestamped filenames
            </p>
          </div>

          {/* Save Button */}
          <div className="flex items-center gap-3 pt-4 border-t">
            <button
              type="button"
              onClick={handleS3ConfigSave}
              disabled={s3Enabled && !s3BucketName.trim()}
              className="btn-primary disabled:opacity-50 disabled:cursor-not-allowed"
            >
              Save S3 Configuration
            </button>
            {s3SaveSuccess && (
              <span className="text-sm text-green-600 font-medium animate-fadeIn">
                ✅ Configuration saved successfully!
              </span>
            )}
            {s3Enabled && !s3BucketName.trim() && (
              <span className="text-sm text-red-600">
                ⚠️ Bucket name is required when S3 export is enabled
              </span>
            )}
          </div>

          {/* Info Card */}
          <div className="bg-blue-50 border-2 border-blue-200 rounded-lg p-4">
            <h4 className="text-sm font-semibold text-blue-900 mb-2">📊 How it works</h4>
            <ul className="text-xs text-blue-800 space-y-1 list-disc list-inside">
              <li>
                When enabled, all export functions (Dashboard, Analytics, Right-Sizing) will automatically upload to this S3 bucket
              </li>
              <li>
                You can still override this setting on individual export pages using the "Upload to S3" toggle
              </li>
              <li>
                Configuration is stored locally in your browser (not sent to server)
              </li>
              <li>
                Each export will return an S3 URL that you can share with your team
              </li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  )
}

// Webhook Create/Edit Modal Component
function WebhookModal({
  webhook,
  onClose,
  onSuccess
}: {
  webhook: TeamsWebhook | null
  onClose: () => void
  onSuccess: () => void
}) {
  const [formData, setFormData] = useState<TeamsWebhookCreate>({
    name: webhook?.name || '',
    description: webhook?.description || '',
    webhook_url: webhook?.webhook_url || '',
    webhook_type: webhook?.webhook_type || 'teams',
    is_active: webhook?.is_active ?? true,
    send_budget_alerts: webhook?.send_budget_alerts ?? true,
    send_cost_summaries: webhook?.send_cost_summaries ?? false,
    send_audit_reports: webhook?.send_audit_reports ?? false,
    budget_threshold_percentage: webhook?.budget_threshold_percentage ?? 80
  })

  const createMutation = useMutation({
    mutationFn: (data: TeamsWebhookCreate) => teamsApi.createWebhook(data),
    onSuccess: () => {
      onSuccess()
    }
  })

  const updateMutation = useMutation({
    mutationFn: (data: TeamsWebhookCreate) => teamsApi.updateWebhook(webhook!.id, data),
    onSuccess: () => {
      onSuccess()
    }
  })

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (webhook) {
      await updateMutation.mutateAsync(formData)
    } else {
      await createMutation.mutateAsync(formData)
    }
  }

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-card max-w-2xl w-full max-h-[90vh] overflow-y-auto shadow-xl">
        <div className="p-6">
          <h2 className="text-2xl font-bold text-modernGray-900 mb-6">
            {webhook ? 'Edit Webhook' : 'Create Webhook'}
          </h2>

          <form onSubmit={handleSubmit} className="space-y-6">
            {/* Name */}
            <div>
              <label className="block text-sm font-medium text-modernGray-700 mb-2">
                Name *
              </label>
              <input
                type="text"
                required
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                className="w-full px-3 py-2 border border-modernGray-300 rounded-button focus:ring-2 focus:ring-brandRed-500 focus:border-transparent"
                placeholder="Production Alerts"
              />
            </div>

            {/* Description */}
            <div>
              <label className="block text-sm font-medium text-modernGray-700 mb-2">
                Description
              </label>
              <textarea
                value={formData.description}
                onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                rows={2}
                className="w-full px-3 py-2 border border-modernGray-300 rounded-button focus:ring-2 focus:ring-brandRed-500 focus:border-transparent"
                placeholder="Webhook for production environment cost alerts"
              />
            </div>

            {/* Webhook URL */}
            <div>
              <label className="block text-sm font-medium text-modernGray-700 mb-2">
                Webhook URL *
              </label>
              <input
                type="url"
                required
                value={formData.webhook_url}
                onChange={(e) => setFormData({ ...formData, webhook_url: e.target.value })}
                className="w-full px-3 py-2 border border-modernGray-300 rounded-button focus:ring-2 focus:ring-brandRed-500 focus:border-transparent font-mono text-sm"
                placeholder="https://outlook.office.com/webhook/..."
              />
              <p className="mt-1 text-xs text-modernGray-500">
                {formData.webhook_type === 'teams'
                  ? 'Get this URL from your Teams channel connector settings (Incoming Webhook)'
                  : 'Get this URL from your Power Automate workflow (HTTP request trigger)'}
              </p>
            </div>

            {/* Webhook Type */}
            <div>
              <label htmlFor="webhook_type" className="block text-sm font-medium text-gray-700 mb-2">
                Webhook Type *
              </label>
              <select
                id="webhook_type"
                value={formData.webhook_type}
                onChange={(e) => setFormData({ ...formData, webhook_type: e.target.value as 'teams' | 'power_automate' })}
                className="w-full px-3 py-2 border border-modernGray-300 rounded-button focus:ring-2 focus:ring-brandRed-500 focus:border-transparent"
              >
                <option value="teams">Microsoft Teams (Incoming Webhook)</option>
                <option value="power_automate">Power Automate (HTTP Workflow)</option>
              </select>
              <p className="mt-1 text-xs text-gray-500">
                {formData.webhook_type === 'teams'
                  ? 'Sends rich adaptive cards to Teams channels'
                  : 'Sends JSON data to Power Automate workflows'}
              </p>
            </div>

            {/* Active Status */}
            <div className="flex items-center">
              <input
                type="checkbox"
                id="is_active"
                checked={formData.is_active}
                onChange={(e) => setFormData({ ...formData, is_active: e.target.checked })}
                className="h-4 w-4 text-brandRed-600 focus:ring-brandRed-500 border-modernGray-300 rounded"
              />
              <label htmlFor="is_active" className="ml-2 block text-sm text-modernGray-700">
                Active (enable notifications)
              </label>
            </div>

            {/* Notification Types */}
            <div>
              <label className="block text-sm font-medium text-modernGray-700 mb-3">
                Notification Types
              </label>
              <div className="space-y-2">
                <div className="flex items-center">
                  <input
                    type="checkbox"
                    id="send_budget_alerts"
                    checked={formData.send_budget_alerts}
                    onChange={(e) => setFormData({ ...formData, send_budget_alerts: e.target.checked })}
                    className="h-4 w-4 text-brandRed-600 focus:ring-brandRed-500 border-modernGray-300 rounded"
                  />
                  <label htmlFor="send_budget_alerts" className="ml-2 block text-sm text-modernGray-700">
                    Budget threshold alerts
                  </label>
                </div>

                {formData.send_budget_alerts && (
                  <div className="ml-6 mt-2">
                    <label className="block text-xs text-modernGray-600 mb-1">
                      Alert when budget reaches:
                    </label>
                    <div className="flex items-center gap-2">
                      <input
                        type="number"
                        min="0"
                        max="100"
                        value={formData.budget_threshold_percentage}
                        onChange={(e) => setFormData({ ...formData, budget_threshold_percentage: parseInt(e.target.value) })}
                        className="w-20 px-2 py-1 border border-modernGray-300 rounded-button text-sm"
                      />
                      <span className="text-sm text-modernGray-600">%</span>
                    </div>
                  </div>
                )}

                <div className="flex items-center">
                  <input
                    type="checkbox"
                    id="send_cost_summaries"
                    checked={formData.send_cost_summaries}
                    onChange={(e) => setFormData({ ...formData, send_cost_summaries: e.target.checked })}
                    className="h-4 w-4 text-brandRed-600 focus:ring-brandRed-500 border-modernGray-300 rounded"
                  />
                  <label htmlFor="send_cost_summaries" className="ml-2 block text-sm text-gray-700">
                    Daily/weekly cost summaries
                  </label>
                </div>

                <div className="flex items-center">
                  <input
                    type="checkbox"
                    id="send_audit_reports"
                    checked={formData.send_audit_reports}
                    onChange={(e) => setFormData({ ...formData, send_audit_reports: e.target.checked })}
                    className="h-4 w-4 text-brandRed-600 focus:ring-brandRed-500 border-modernGray-300 rounded"
                  />
                  <label htmlFor="send_audit_reports" className="ml-2 block text-sm text-gray-700">
                    FinOps audit reports
                  </label>
                </div>
              </div>
            </div>

            {/* Actions */}
            <div className="flex gap-3 pt-4">
              <button
                type="submit"
                disabled={createMutation.isPending || updateMutation.isPending}
                className="flex-1 btn-primary disabled:opacity-50"
              >
                {createMutation.isPending || updateMutation.isPending
                  ? 'Saving...'
                  : webhook
                  ? 'Update Webhook'
                  : 'Create Webhook'}
              </button>
              <button
                type="button"
                onClick={onClose}
                className="btn-secondary"
              >
                Cancel
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  )
}
