import api from './axios'

export interface AWSAccountCreate {
  name: string
  description?: string
  access_key_id: string
  secret_access_key: string
  region?: string
}

export interface AWSAccountUpdate {
  name?: string
  description?: string
  access_key_id?: string
  secret_access_key?: string
  region?: string
  is_active?: boolean
}

export interface AWSAccount {
  id: number
  name: string
  description?: string
  account_id?: string
  region: string
  is_active: boolean
  last_validated?: string
  validation_error?: string
  created_at: string
  updated_at?: string
}

export const awsAccountsApi = {
  /**
   * Create a new AWS account
   */
  create: async (data: AWSAccountCreate): Promise<AWSAccount> => {
    const response = await api.post('/aws-accounts/', data)
    return response.data
  },

  /**
   * List all AWS accounts
   */
  list: async (activeOnly: boolean = true): Promise<AWSAccount[]> => {
    const response = await api.get('/aws-accounts/', {
      params: { active_only: activeOnly },
    })
    return response.data
  },

  /**
   * Get a specific AWS account
   */
  get: async (accountId: number): Promise<AWSAccount> => {
    const response = await api.get(`/aws-accounts/${accountId}`)
    return response.data
  },

  /**
   * Update an AWS account
   */
  update: async (accountId: number, data: AWSAccountUpdate): Promise<AWSAccount> => {
    const response = await api.put(`/aws-accounts/${accountId}`, data)
    return response.data
  },

  /**
   * Delete an AWS account
   */
  delete: async (accountId: number): Promise<void> => {
    await api.delete(`/aws-accounts/${accountId}`)
  },

  /**
   * Validate an AWS account
   */
  validate: async (accountId: number) => {
    const response = await api.post(`/aws-accounts/${accountId}/validate`)
    return response.data
  },
}
