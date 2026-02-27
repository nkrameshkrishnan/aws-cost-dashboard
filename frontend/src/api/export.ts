/**
 * Export API client for generating reports.
 */
import axios from './axios'
import type { FullAuditResults } from '@/types/audit'

export interface ExportOptions {
  jobId?: string
  auditResults?: FullAuditResults
  uploadToS3?: boolean
  s3Bucket?: string
}

export interface CostExportRequest {
  profile_name: string
  start_date: string
  end_date: string
  export_format: 'csv' | 'json'
  upload_to_s3?: boolean
  s3_bucket?: string
}

export interface RightSizingExportRequest {
  profile_name: string
  resource_types?: string
  export_format: 'csv' | 'json' | 'excel'
  upload_to_s3?: boolean
  s3_bucket?: string
}

export interface UnitCostExportRequest {
  profile_name: string
  start_date: string
  end_date: string
  region?: string
  export_format: 'csv' | 'json'
  upload_to_s3?: boolean
  s3_bucket?: string
}

export interface ExportResponse {
  success: boolean
  message: string
  file_name?: string
  file_size?: number
  s3_url?: string
  s3_bucket?: string
  s3_key?: string
}

export const exportApi = {
  /**
   * Generate and download PDF audit report.
   */
  async exportAuditPDF(options: ExportOptions): Promise<Blob | ExportResponse> {
    const params = options.jobId ? { job_id: options.jobId } : {}

    const requestBody = {
      audit_results: options.auditResults,
      upload_to_s3: options.uploadToS3 || false,
      s3_bucket: options.s3Bucket,
    }

    const response = await axios.post('/export/audit/pdf', requestBody, {
      params,
      responseType: options.uploadToS3 ? 'json' : 'blob',
    })

    return response.data
  },

  /**
   * Generate and download Excel audit report.
   */
  async exportAuditExcel(options: ExportOptions): Promise<Blob | ExportResponse> {
    const params = options.jobId ? { job_id: options.jobId } : {}

    const requestBody = {
      audit_results: options.auditResults,
      upload_to_s3: options.uploadToS3 || false,
      s3_bucket: options.s3Bucket,
    }

    const response = await axios.post('/export/audit/excel', requestBody, {
      params,
      responseType: options.uploadToS3 ? 'json' : 'blob',
    })

    return response.data
  },

  /**
   * Generate and download CSV for specific audit type.
   */
  async exportAuditCSV(jobId: string, auditType: string): Promise<Blob> {
    const response = await axios.post(
      '/export/audit/csv',
      {},
      {
        params: {
          job_id: jobId,
          audit_type: auditType,
        },
        responseType: 'blob',
      }
    )

    return response.data
  },

  /**
   * Helper function to trigger browser download of a blob.
   */
  downloadBlob(blob: Blob, fileName: string) {
    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = fileName
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    window.URL.revokeObjectURL(url)
  },

  /**
   * Generate file name for audit export.
   */
  generateFileName(accountName: string, format: 'pdf' | 'xlsx' | 'csv', auditType?: string): string {
    const timestamp = new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19)
    const safeAccountName = accountName.replace(/[^a-zA-Z0-9]/g, '_')

    if (auditType) {
      return `finops_${auditType}_${safeAccountName}_${timestamp}.${format}`
    }

    return `finops_audit_${safeAccountName}_${timestamp}.${format}`
  },

  // ==================== Cost Data Exports ====================

  /**
   * Export daily costs to CSV or JSON.
   */
  async exportDailyCosts(request: CostExportRequest): Promise<Blob | ExportResponse> {
    const response = await axios.post('/export/costs/daily', request, {
      responseType: request.upload_to_s3 ? 'json' : 'blob',
    })

    return response.data
  },

  /**
   * Export service breakdown costs to CSV or JSON.
   */
  async exportServiceBreakdown(request: CostExportRequest): Promise<Blob | ExportResponse> {
    const response = await axios.post('/export/costs/by-service', request, {
      responseType: request.upload_to_s3 ? 'json' : 'blob',
    })

    return response.data
  },

  // ==================== Right-Sizing Exports ====================

  /**
   * Export right-sizing recommendations.
   */
  async exportRightSizing(request: RightSizingExportRequest): Promise<Blob | ExportResponse> {
    const response = await axios.post('/export/rightsizing', request, {
      responseType: request.upload_to_s3 ? 'json' : 'blob',
    })

    return response.data
  },

  // ==================== Unit Cost Exports ====================

  /**
   * Export unit cost metrics to CSV or JSON.
   */
  async exportUnitCosts(request: UnitCostExportRequest): Promise<Blob | ExportResponse> {
    const response = await axios.post('/export/unit-costs', request, {
      responseType: request.upload_to_s3 ? 'json' : 'blob',
    })

    return response.data
  },

  // ==================== Analytics Exports ====================

  /**
   * Export forecast data to CSV or JSON.
   */
  async exportForecast(
    profileName: string,
    startDate: string,
    endDate: string,
    days: number = 30,
    format: 'csv' | 'json' = 'csv',
    uploadToS3: boolean = false,
    s3Bucket?: string
  ): Promise<Blob | ExportResponse> {
    const request = {
      profile_name: profileName,
      start_date: startDate,
      end_date: endDate,
      data_type: 'forecast',
      export_format: format,
      upload_to_s3: uploadToS3,
      s3_bucket: s3Bucket,
    }

    const response = await axios.post('/export/analytics/forecast', request, {
      params: { days },
      responseType: uploadToS3 ? 'json' : 'blob',
    })

    return response.data
  },

  /**
   * Export anomaly detection results to CSV or JSON.
   */
  async exportAnomalies(
    profileName: string,
    startDate: string,
    endDate: string,
    format: 'csv' | 'json' = 'csv',
    uploadToS3: boolean = false,
    s3Bucket?: string
  ): Promise<Blob | ExportResponse> {
    const request = {
      profile_name: profileName,
      start_date: startDate,
      end_date: endDate,
      data_type: 'anomalies',
      export_format: format,
      upload_to_s3: uploadToS3,
      s3_bucket: s3Bucket,
    }

    const response = await axios.post('/export/analytics/anomalies', request, {
      responseType: uploadToS3 ? 'json' : 'blob',
    })

    return response.data
  },

  /**
   * Generate file name for cost/analytics/rightsizing exports.
   */
  generateExportFileName(
    dataType: string,
    profileName: string,
    format: 'csv' | 'json' | 'xlsx' | 'pdf'
  ): string {
    const timestamp = new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19)
    const safeProfileName = profileName.replace(/[^a-zA-Z0-9]/g, '_')
    return `${dataType}_${safeProfileName}_${timestamp}.${format}`
  },

  // ==================== Cost PDF/Excel Exports ====================

  /**
   * Export cost data to PDF.
   */
  async exportCostPDF(
    profileName: string,
    startDate: string,
    endDate: string,
    uploadToS3: boolean = false,
    s3Bucket?: string
  ): Promise<Blob | ExportResponse> {
    const request = {
      profile_name: profileName,
      start_date: startDate,
      end_date: endDate,
      export_format: 'pdf',
      upload_to_s3: uploadToS3,
      s3_bucket: s3Bucket,
    }

    const response = await axios.post('/export/costs/pdf', request, {
      responseType: uploadToS3 ? 'json' : 'blob',
    })

    return response.data
  },

  /**
   * Export cost data to Excel.
   */
  async exportCostExcel(
    profileName: string,
    startDate: string,
    endDate: string,
    uploadToS3: boolean = false,
    s3Bucket?: string
  ): Promise<Blob | ExportResponse> {
    const request = {
      profile_name: profileName,
      start_date: startDate,
      end_date: endDate,
      export_format: 'xlsx',
      upload_to_s3: uploadToS3,
      s3_bucket: s3Bucket,
    }

    const response = await axios.post('/export/costs/excel', request, {
      responseType: uploadToS3 ? 'json' : 'blob',
    })

    return response.data
  },

  // ==================== Forecast PDF/Excel Exports ====================

  /**
   * Export forecast data to PDF.
   */
  async exportForecastPDF(
    profileName: string,
    startDate: string,
    endDate: string,
    days: number = 30,
    uploadToS3: boolean = false,
    s3Bucket?: string
  ): Promise<Blob | ExportResponse> {
    const request = {
      profile_name: profileName,
      start_date: startDate,
      end_date: endDate,
      data_type: 'forecast',
      export_format: 'pdf',
      upload_to_s3: uploadToS3,
      s3_bucket: s3Bucket,
    }

    const response = await axios.post('/export/forecast/pdf', request, {
      params: { days },
      responseType: uploadToS3 ? 'json' : 'blob',
    })

    return response.data
  },

  /**
   * Export forecast data to Excel.
   */
  async exportForecastExcel(
    profileName: string,
    startDate: string,
    endDate: string,
    days: number = 30,
    uploadToS3: boolean = false,
    s3Bucket?: string
  ): Promise<Blob | ExportResponse> {
    const request = {
      profile_name: profileName,
      start_date: startDate,
      end_date: endDate,
      data_type: 'forecast',
      export_format: 'xlsx',
      upload_to_s3: uploadToS3,
      s3_bucket: s3Bucket,
    }

    const response = await axios.post('/export/forecast/excel', request, {
      params: { days },
      responseType: uploadToS3 ? 'json' : 'blob',
    })

    return response.data
  },

  // ==================== Right-Sizing PDF/Excel Exports ====================

  /**
   * Export right-sizing recommendations to PDF.
   */
  async exportRightSizingPDF(
    profileName: string,
    resourceTypes?: string,
    uploadToS3: boolean = false,
    s3Bucket?: string
  ): Promise<Blob | ExportResponse> {
    const request = {
      profile_name: profileName,
      resource_types: resourceTypes,
      export_format: 'pdf',
      upload_to_s3: uploadToS3,
      s3_bucket: s3Bucket,
    }

    const response = await axios.post('/export/rightsizing/pdf', request, {
      responseType: uploadToS3 ? 'json' : 'blob',
    })

    return response.data
  },

  /**
   * Export right-sizing recommendations to Excel.
   */
  async exportRightSizingExcel(
    profileName: string,
    resourceTypes?: string,
    uploadToS3: boolean = false,
    s3Bucket?: string
  ): Promise<Blob | ExportResponse> {
    const request = {
      profile_name: profileName,
      resource_types: resourceTypes,
      export_format: 'xlsx',
      upload_to_s3: uploadToS3,
      s3_bucket: s3Bucket,
    }

    const response = await axios.post('/export/rightsizing/excel', request, {
      responseType: uploadToS3 ? 'json' : 'blob',
    })

    return response.data
  },
}
