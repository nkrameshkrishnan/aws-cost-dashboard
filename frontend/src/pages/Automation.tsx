import { useState, useEffect } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { automationApi, Job, ScheduleAuditRequest, ScheduleBudgetAlertsRequest } from '@/api/automation'
import { useProfileStore } from '@/store/profileStore'
import {
  Clock,
  Play,
  Pause,
  Trash2,
  Plus,
  RefreshCw,
  CheckCircle,
  XCircle,
  AlertCircle,
  Calendar,
  Settings,
  Zap,
} from 'lucide-react'
import { LoadingSpinner } from '@/components/common/LoadingSpinner'

export function Automation() {
  const queryClient = useQueryClient()
  const { selectedProfile } = useProfileStore()
  const [showCreateModal, setShowCreateModal] = useState(false)
  const [jobType, setJobType] = useState<'budget' | 'audit'>('budget')

  // Fetch scheduled jobs
  const { data: jobsData, isLoading } = useQuery({
    queryKey: ['automation-jobs'],
    queryFn: () => automationApi.listJobs(),
    refetchInterval: 30000, // Refresh every 30 seconds
  })

  // Fetch scheduler status
  const { data: statusData } = useQuery({
    queryKey: ['automation-status'],
    queryFn: () => automationApi.getSchedulerStatus(),
    refetchInterval: 30000,
  })

  // Pause job mutation
  const pauseMutation = useMutation({
    mutationFn: (jobId: string) => automationApi.pauseJob(jobId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['automation-jobs'] })
      alert('✅ Job paused successfully')
    },
    onError: (error: any) => {
      alert(`❌ Failed to pause job: ${error.response?.data?.detail || error.message}`)
    },
  })

  // Resume job mutation
  const resumeMutation = useMutation({
    mutationFn: (jobId: string) => automationApi.resumeJob(jobId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['automation-jobs'] })
      alert('✅ Job resumed successfully')
    },
    onError: (error: any) => {
      alert(`❌ Failed to resume job: ${error.response?.data?.detail || error.message}`)
    },
  })

  // Delete job mutation
  const deleteMutation = useMutation({
    mutationFn: (jobId: string) => automationApi.deleteJob(jobId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['automation-jobs'] })
      alert('✅ Job deleted successfully')
    },
    onError: (error: any) => {
      alert(`❌ Failed to delete job: ${error.response?.data?.detail || error.message}`)
    },
  })

  // Run job now mutation
  const runNowMutation = useMutation({
    mutationFn: (jobId: string) => automationApi.runJobNow(jobId),
    onSuccess: () => {
      alert('✅ Job executed successfully')
    },
    onError: (error: any) => {
      alert(`❌ Failed to run job: ${error.response?.data?.detail || error.message}`)
    },
  })

  const formatNextRunTime = (time: string | null) => {
    if (!time) return 'Paused'
    const date = new Date(time)
    const now = new Date()
    const diff = date.getTime() - now.getTime()
    const hours = Math.floor(diff / 1000 / 60 / 60)
    const minutes = Math.floor((diff / 1000 / 60) % 60)

    if (diff < 0) return 'Overdue'
    if (hours > 24) return `In ${Math.floor(hours / 24)} days`
    if (hours > 0) return `In ${hours}h ${minutes}m`
    return `In ${minutes}m`
  }

  const getJobIcon = (jobName: string) => {
    if (jobName.includes('Budget')) return <AlertCircle className="w-5 h-5 text-modernYellow-600" />
    if (jobName.includes('Audit')) return <Settings className="w-5 h-5 text-modernTeal-600" />
    return <Zap className="w-5 h-5 text-trendRed-700" />
  }

  return (
    <div className="container mx-auto px-4 py-8">
      {/* Header */}
      <div className="mb-8 flex justify-between items-start">
        <div>
          <h1 className="text-3xl font-bold text-modernGray-900 tracking-tight flex items-center gap-3">
            <Zap className="w-8 h-8 text-trendRed-700" />
            Automation
          </h1>
          <p className="text-modernGray-600 mt-2">Manage scheduled jobs and automated tasks</p>
        </div>

        <button
          onClick={() => setShowCreateModal(true)}
          className="btn-primary flex items-center gap-2"
        >
          <Plus className="w-4 h-4" />
          Create Job
        </button>
      </div>

      {/* Scheduler Status */}
      {statusData && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-6">
          <div className="card border-l-4 border-l-modernGreen-600">
            <div className="flex items-center gap-3 mb-2">
              <div className="p-2 bg-modernGreen-100 rounded-card">
                {statusData.running ? (
                  <CheckCircle className="w-5 h-5 text-modernGreen-600" />
                ) : (
                  <XCircle className="w-5 h-5 text-modernRed-600" />
                )}
              </div>
              <h3 className="text-sm font-semibold text-modernGray-500 uppercase">Scheduler Status</h3>
            </div>
            <p className={`text-3xl font-bold ${statusData.running ? 'text-modernGreen-600' : 'text-modernRed-600'}`}>
              {statusData.running ? 'Running' : 'Stopped'}
            </p>
          </div>

          <div className="card border-l-4 border-l-modernTeal-600">
            <div className="flex items-center gap-3 mb-2">
              <div className="p-2 bg-modernTeal-100 rounded-card">
                <Calendar className="w-5 h-5 text-modernTeal-600" />
              </div>
              <h3 className="text-sm font-semibold text-modernGray-500 uppercase">Total Jobs</h3>
            </div>
            <p className="text-3xl font-bold text-modernGray-900">{statusData.total_jobs}</p>
          </div>

          <div className="card border-l-4 border-l-trendRed-700">
            <div className="flex items-center gap-3 mb-2">
              <div className="p-2 bg-trendRed-100 rounded-card">
                <Play className="w-5 h-5 text-trendRed-700" />
              </div>
              <h3 className="text-sm font-semibold text-modernGray-500 uppercase">Active Jobs</h3>
            </div>
            <p className="text-3xl font-bold text-modernGray-900">{statusData.active_jobs}</p>
          </div>
        </div>
      )}

      {/* Jobs List */}
      <div className="card">
        <div className="border-b border-modernGray-200 px-6 py-4">
          <h2 className="text-xl font-bold text-modernGray-900 flex items-center gap-2">
            <Clock className="w-5 h-5 text-trendRed-700" />
            Scheduled Jobs
          </h2>
        </div>

        {isLoading ? (
          <div className="p-12">
            <LoadingSpinner size="lg" text="Loading jobs..." />
          </div>
        ) : !jobsData || jobsData.jobs.length === 0 ? (
          <div className="p-12 text-center">
            <Calendar className="w-16 h-16 text-modernGray-300 mx-auto mb-4" />
            <h3 className="text-lg font-semibold text-modernGray-700 mb-2">No Scheduled Jobs</h3>
            <p className="text-modernGray-500 mb-6">Create your first automated job to get started</p>
            <button
              onClick={() => setShowCreateModal(true)}
              className="btn-primary"
            >
              Create Job
            </button>
          </div>
        ) : (
          <div className="divide-y divide-modernGray-200">
            {jobsData.jobs.map((job) => (
              <div
                key={job.job_id}
                className="p-6 hover:bg-modernGray-50 transition-colors"
              >
                <div className="flex items-start justify-between">
                  <div className="flex items-start gap-4 flex-1">
                    <div className="mt-1">{getJobIcon(job.name)}</div>
                    <div className="flex-1">
                      <h3 className="text-lg font-semibold text-modernGray-900 mb-1">{job.name}</h3>
                      <p className="text-sm text-modernGray-500 font-mono mb-3">ID: {job.job_id}</p>

                      <div className="flex flex-wrap gap-4 text-sm">
                        <div className="flex items-center gap-2">
                          <Clock className="w-4 h-4 text-modernGray-400" />
                          <span className="text-modernGray-600">
                            Next run: <span className="font-semibold">{formatNextRunTime(job.next_run_time)}</span>
                          </span>
                        </div>

                        {job.next_run_time && (
                          <div className="flex items-center gap-2">
                            <Calendar className="w-4 h-4 text-modernGray-400" />
                            <span className="text-modernGray-600">
                              {new Date(job.next_run_time).toLocaleString()}
                            </span>
                          </div>
                        )}

                        {job.trigger && (
                          <div className="flex items-center gap-2">
                            <Settings className="w-4 h-4 text-modernGray-400" />
                            <span className="text-modernGray-600 font-mono text-xs">{job.trigger}</span>
                          </div>
                        )}
                      </div>

                      <div className="mt-3">
                        <span
                          className={`px-3 py-1 rounded-full text-xs font-semibold ${
                            job.enabled
                              ? 'bg-modernGreen-100 text-modernGreen-700'
                              : 'bg-modernGray-100 text-modernGray-700'
                          }`}
                        >
                          {job.enabled ? 'Active' : 'Paused'}
                        </span>
                      </div>
                    </div>
                  </div>

                  {/* Actions */}
                  <div className="flex items-center gap-2 ml-4">
                    <button
                      onClick={() => runNowMutation.mutate(job.job_id)}
                      disabled={runNowMutation.isPending}
                      className="p-2 text-modernTeal-600 hover:bg-modernTeal-50 rounded-button transition-colors disabled:opacity-50"
                      title="Run now"
                    >
                      <Play className="w-5 h-5" />
                    </button>

                    {job.enabled ? (
                      <button
                        onClick={() => pauseMutation.mutate(job.job_id)}
                        disabled={pauseMutation.isPending}
                        className="p-2 text-modernYellow-600 hover:bg-modernYellow-50 rounded-button transition-colors disabled:opacity-50"
                        title="Pause"
                      >
                        <Pause className="w-5 h-5" />
                      </button>
                    ) : (
                      <button
                        onClick={() => resumeMutation.mutate(job.job_id)}
                        disabled={resumeMutation.isPending}
                        className="p-2 text-modernGreen-600 hover:bg-modernGreen-50 rounded-button transition-colors disabled:opacity-50"
                        title="Resume"
                      >
                        <Play className="w-5 h-5" />
                      </button>
                    )}

                    <button
                      onClick={() => {
                        if (confirm(`Delete job "${job.name}"?`)) {
                          deleteMutation.mutate(job.job_id)
                        }
                      }}
                      disabled={deleteMutation.isPending}
                      className="p-2 text-modernRed-600 hover:bg-modernRed-50 rounded-button transition-colors disabled:opacity-50"
                      title="Delete"
                    >
                      <Trash2 className="w-5 h-5" />
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Create Job Modal */}
      {showCreateModal && (
        <CreateJobModal
          jobType={jobType}
          setJobType={setJobType}
          onClose={() => setShowCreateModal(false)}
          onSuccess={() => {
            setShowCreateModal(false)
            queryClient.invalidateQueries({ queryKey: ['automation-jobs'] })
          }}
          selectedProfile={selectedProfile}
        />
      )}
    </div>
  )
}

// Create Job Modal Component
function CreateJobModal({
  jobType,
  setJobType,
  onClose,
  onSuccess,
  selectedProfile,
}: {
  jobType: 'budget' | 'audit'
  setJobType: (type: 'budget' | 'audit') => void
  onClose: () => void
  onSuccess: () => void
  selectedProfile: string
}) {
  const [jobId, setJobId] = useState('')
  const [cronExpression, setCronExpression] = useState('0 */6 * * *')
  const [auditTypes, setAuditTypes] = useState<string[]>([
    'ec2',
    'ebs',
    'rds',
    'lambda',
    's3',
    'lb',
  ])
  const [sendNotification, setSendNotification] = useState(true)

  const createBudgetJobMutation = useMutation({
    mutationFn: (data: ScheduleBudgetAlertsRequest) => automationApi.scheduleBudgetAlerts(data),
    onSuccess: () => {
      alert('✅ Budget alerts job created successfully')
      onSuccess()
    },
    onError: (error: any) => {
      alert(`❌ Failed to create job: ${error.response?.data?.detail || error.message}`)
    },
  })

  const createAuditJobMutation = useMutation({
    mutationFn: (data: ScheduleAuditRequest) => automationApi.scheduleAudit(data),
    onSuccess: () => {
      alert('✅ Audit job created successfully')
      onSuccess()
    },
    onError: (error: any) => {
      alert(`❌ Failed to create job: ${error.response?.data?.detail || error.message}`)
    },
  })

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()

    if (jobType === 'budget') {
      createBudgetJobMutation.mutate({
        job_id: jobId || undefined,
        cron_expression: cronExpression,
        enabled: true,
      })
    } else {
      createAuditJobMutation.mutate({
        job_id: jobId,
        account_name: selectedProfile,
        cron_expression: cronExpression,
        audit_types: auditTypes,
        send_teams_notification: sendNotification,
        enabled: true,
      })
    }
  }

  const cronPresets = [
    { label: 'Every hour', value: '0 * * * *' },
    { label: 'Every 6 hours', value: '0 */6 * * *' },
    { label: 'Daily at 2 AM', value: '0 2 * * *' },
    { label: 'Weekly (Monday 2 AM)', value: '0 2 * * 1' },
    { label: 'Monthly (1st at 2 AM)', value: '0 2 1 * *' },
  ]

  const allAuditTypes = [
    'ec2', 'ebs', 'eip', 'tagging', 'rds', 'lambda', 's3', 'lb',
    'nat_gateway', 'elasticache', 'cloudwatch_logs', 'dynamodb', 'savings_plans',
    'vpc_endpoint', 'efs', 'ebs_snapshot', 'data_transfer', 'beanstalk',
    'cloudfront', 'route53', 'sqs', 'sns', 'apigateway', 'stepfunctions',
    'ecs', 'redshift', 'kinesis', 'glue',
  ]

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-card max-w-2xl w-full max-h-[90vh] overflow-y-auto shadow-xl">
        <div className="p-6 border-b border-modernGray-200">
          <h2 className="text-2xl font-bold text-modernGray-900">Create Scheduled Job</h2>
        </div>

        <form onSubmit={handleSubmit} className="p-6 space-y-6">
          {/* Job Type Selection */}
          <div>
            <label className="block text-sm font-medium text-modernGray-700 mb-2">Job Type</label>
            <div className="grid grid-cols-2 gap-4">
              <button
                type="button"
                onClick={() => setJobType('budget')}
                className={`p-4 border-2 rounded-card transition-all ${
                  jobType === 'budget'
                    ? 'border-trendRed-700 bg-trendRed-50'
                    : 'border-modernGray-200 hover:border-modernGray-300'
                }`}
              >
                <AlertCircle className="w-6 h-6 text-modernYellow-600 mx-auto mb-2" />
                <p className="font-semibold">Budget Alerts</p>
                <p className="text-xs text-modernGray-500 mt-1">Check budgets periodically</p>
              </button>

              <button
                type="button"
                onClick={() => setJobType('audit')}
                className={`p-4 border-2 rounded-card transition-all ${
                  jobType === 'audit'
                    ? 'border-trendRed-700 bg-trendRed-50'
                    : 'border-modernGray-200 hover:border-modernGray-300'
                }`}
              >
                <Settings className="w-6 h-6 text-modernTeal-600 mx-auto mb-2" />
                <p className="font-semibold">FinOps Audit</p>
                <p className="text-xs text-modernGray-500 mt-1">Run cost audits automatically</p>
              </button>
            </div>
          </div>

          {/* Job ID */}
          <div>
            <label className="block text-sm font-medium text-modernGray-700 mb-2">
              Job ID {jobType === 'budget' && '(optional)'}
            </label>
            <input
              type="text"
              value={jobId}
              onChange={(e) => setJobId(e.target.value)}
              placeholder={jobType === 'budget' ? 'budget-alerts-default' : 'audit-prod-daily'}
              required={jobType === 'audit'}
              className="w-full px-3 py-2 border border-modernGray-300 rounded-button focus:ring-2 focus:ring-trendRed-500 focus:border-transparent"
            />
            <p className="text-xs text-modernGray-500 mt-1">Unique identifier for this job</p>
          </div>

          {/* Cron Expression */}
          <div>
            <label className="block text-sm font-medium text-modernGray-700 mb-2">Schedule (Cron Expression)</label>
            <select
              value={cronExpression}
              onChange={(e) => setCronExpression(e.target.value)}
              className="w-full px-3 py-2 border border-modernGray-300 rounded-button focus:ring-2 focus:ring-trendRed-500 focus:border-transparent mb-2"
            >
              {cronPresets.map((preset) => (
                <option key={preset.value} value={preset.value}>
                  {preset.label} ({preset.value})
                </option>
              ))}
              <option value="custom">Custom...</option>
            </select>

            {cronExpression === 'custom' && (
              <input
                type="text"
                placeholder="0 2 * * *"
                onChange={(e) => setCronExpression(e.target.value)}
                className="w-full px-3 py-2 border border-modernGray-300 rounded-button focus:ring-2 focus:ring-trendRed-500 focus:border-transparent"
              />
            )}

            <p className="text-xs text-modernGray-500 mt-1">
              Format: minute hour day month day_of_week
            </p>
          </div>

          {/* Audit-specific fields */}
          {jobType === 'audit' && (
            <>
              <div>
                <label className="block text-sm font-medium text-modernGray-700 mb-2">
                  AWS Account
                </label>
                <input
                  type="text"
                  value={selectedProfile}
                  disabled
                  className="w-full px-3 py-2 border border-modernGray-300 rounded-button bg-modernGray-50 text-modernGray-700"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-modernGray-700 mb-2">
                  Audit Types ({auditTypes.length} selected)
                </label>
                <div className="grid grid-cols-3 gap-2 max-h-48 overflow-y-auto p-3 border border-modernGray-200 rounded-card">
                  {allAuditTypes.map((type) => (
                    <label key={type} className="flex items-center gap-2 text-sm">
                      <input
                        type="checkbox"
                        checked={auditTypes.includes(type)}
                        onChange={(e) => {
                          if (e.target.checked) {
                            setAuditTypes([...auditTypes, type])
                          } else {
                            setAuditTypes(auditTypes.filter((t) => t !== type))
                          }
                        }}
                        className="rounded text-trendRed-600 focus:ring-trendRed-500"
                      />
                      <span className="text-modernGray-700">{type}</span>
                    </label>
                  ))}
                </div>
              </div>

              <div>
                <label className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    checked={sendNotification}
                    onChange={(e) => setSendNotification(e.target.checked)}
                    className="rounded text-trendRed-600 focus:ring-trendRed-500"
                  />
                  <span className="text-sm font-medium text-modernGray-700">
                    Send Teams notification when audit completes
                  </span>
                </label>
              </div>
            </>
          )}

          {/* Actions */}
          <div className="flex gap-3 pt-4">
            <button
              type="submit"
              disabled={createBudgetJobMutation.isPending || createAuditJobMutation.isPending}
              className="flex-1 btn-primary disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {createBudgetJobMutation.isPending || createAuditJobMutation.isPending
                ? 'Creating...'
                : 'Create Job'}
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
  )
}
