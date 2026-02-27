/**
 * API client for Microsoft Teams webhook integration.
 */
import axios from './axios'
import type {
  TeamsWebhook,
  TeamsWebhookCreate,
  TeamsWebhookUpdate,
  TeamsWebhookTestRequest,
  TeamsWebhookTestResponse,
  TeamsSendNotificationRequest,
  TeamsSendNotificationResponse
} from '@/types/teams'

export const teamsApi = {
  /**
   * Create a new Teams webhook.
   */
  async createWebhook(webhook: TeamsWebhookCreate): Promise<TeamsWebhook> {
    const response = await axios.post('/teams/webhooks', webhook)
    return response.data
  },

  /**
   * List all Teams webhooks.
   */
  async listWebhooks(): Promise<TeamsWebhook[]> {
    const response = await axios.get('/teams/webhooks')
    return response.data
  },

  /**
   * Get a specific Teams webhook.
   */
  async getWebhook(id: number): Promise<TeamsWebhook> {
    const response = await axios.get(`/teams/webhooks/${id}`)
    return response.data
  },

  /**
   * Update a Teams webhook.
   */
  async updateWebhook(id: number, webhook: TeamsWebhookUpdate): Promise<TeamsWebhook> {
    const response = await axios.put(`/teams/webhooks/${id}`, webhook)
    return response.data
  },

  /**
   * Delete a Teams webhook.
   */
  async deleteWebhook(id: number): Promise<void> {
    await axios.delete(`/teams/webhooks/${id}`)
  },

  /**
   * Test a Teams webhook URL.
   */
  async testWebhook(request: TeamsWebhookTestRequest): Promise<TeamsWebhookTestResponse> {
    const response = await axios.post('/teams/test', request)
    return response.data
  },

  /**
   * Send a notification to a Teams webhook.
   */
  async sendNotification(request: TeamsSendNotificationRequest): Promise<TeamsSendNotificationResponse> {
    const response = await axios.post('/teams/send', request)
    return response.data
  },

  /**
   * Check all budgets and send Teams alerts for those exceeding thresholds.
   */
  async checkBudgetAlerts(): Promise<{
    success: boolean
    message: string
    webhooks_checked: number
    budgets_checked: number
    notifications_sent: number
    errors: string[]
  }> {
    const response = await axios.post('/teams/budget-alerts/check')
    return response.data
  },

  /**
   * Send immediate budget alert for a specific budget.
   */
  async sendBudgetAlert(budgetId: number): Promise<{
    success: boolean
    message: string
    notifications_sent: number
    webhooks_checked: number
    errors: string[]
  }> {
    const response = await axios.post(`/teams/budget-alerts/${budgetId}`)
    return response.data
  }
}
