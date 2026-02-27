/**
 * TypeScript types for Microsoft Teams webhook integration.
 */

export interface TeamsWebhook {
  id: number
  name: string
  description?: string
  webhook_url: string
  webhook_type: 'teams' | 'power_automate'
  is_active: boolean
  send_budget_alerts: boolean
  send_cost_summaries: boolean
  send_audit_reports: boolean
  budget_threshold_percentage: number
  created_at: string
  updated_at?: string
  last_sent_at?: string
}

export interface TeamsWebhookCreate {
  name: string
  description?: string
  webhook_url: string
  webhook_type?: 'teams' | 'power_automate'
  is_active?: boolean
  send_budget_alerts?: boolean
  send_cost_summaries?: boolean
  send_audit_reports?: boolean
  budget_threshold_percentage?: number
}

export interface TeamsWebhookUpdate {
  name?: string
  description?: string
  webhook_url?: string
  webhook_type?: 'teams' | 'power_automate'
  is_active?: boolean
  send_budget_alerts?: boolean
  send_cost_summaries?: boolean
  send_audit_reports?: boolean
  budget_threshold_percentage?: number
}

export interface TeamsWebhookTestRequest {
  webhook_url: string
  webhook_type?: 'teams' | 'power_automate'
}

export interface TeamsWebhookTestResponse {
  success: boolean
  message: string
}

export interface TeamsSendNotificationRequest {
  webhook_id: number
  notification_type: 'budget_alert' | 'cost_summary' | 'audit_report' | 'custom'
  data: Record<string, any>
}

export interface TeamsSendNotificationResponse {
  success: boolean
  message: string
  webhook_name: string
}
