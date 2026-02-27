import { Fragment, useState } from 'react'
import { Dialog, Transition } from '@headlessui/react'
import { X, Download, FileText, FileSpreadsheet, FileJson, Upload, CheckCircle, XCircle } from 'lucide-react'
import { exportApi } from '@/api/export'
import type {
  CostExportRequest,
  RightSizingExportRequest,
  UnitCostExportRequest,
  ExportResponse,
} from '@/api/export'

export interface ExportDialogProps {
  isOpen: boolean
  onClose: () => void
  exportType: 'daily_costs' | 'service_breakdown' | 'rightsizing' | 'unit_costs' | 'forecast' | 'anomalies'
  profileName: string
  startDate?: string
  endDate?: string
  region?: string
  resourceTypes?: string
  forecastDays?: number
}

export function ExportDialog({
  isOpen,
  onClose,
  exportType,
  profileName,
  startDate,
  endDate,
  region,
  resourceTypes,
  forecastDays = 30,
}: ExportDialogProps) {
  const [selectedFormat, setSelectedFormat] = useState<'csv' | 'json' | 'excel'>('csv')
  const [uploadToS3, setUploadToS3] = useState(false)
  const [s3Bucket, setS3Bucket] = useState('')
  const [isExporting, setIsExporting] = useState(false)
  const [exportStatus, setExportStatus] = useState<{
    success?: boolean
    message?: string
    s3_url?: string
  } | null>(null)

  const getExportTitle = () => {
    switch (exportType) {
      case 'daily_costs':
        return 'Export Daily Costs'
      case 'service_breakdown':
        return 'Export Service Breakdown'
      case 'rightsizing':
        return 'Export Right-Sizing Recommendations'
      case 'unit_costs':
        return 'Export Unit Cost Metrics'
      case 'forecast':
        return 'Export Forecast Data'
      case 'anomalies':
        return 'Export Anomaly Detection Results'
      default:
        return 'Export Data'
    }
  }

  const getAvailableFormats = () => {
    if (exportType === 'rightsizing') {
      return ['csv', 'json', 'excel']
    }
    return ['csv', 'json']
  }

  const handleExport = async () => {
    if (!startDate || !endDate) {
      setExportStatus({
        success: false,
        message: 'Start date and end date are required',
      })
      return
    }

    setIsExporting(true)
    setExportStatus(null)

    try {
      let result: Blob | ExportResponse

      // Build request based on export type
      switch (exportType) {
        case 'daily_costs': {
          const request: CostExportRequest = {
            profile_name: profileName,
            start_date: startDate,
            end_date: endDate,
            export_format: selectedFormat as 'csv' | 'json',
            upload_to_s3: uploadToS3,
            s3_bucket: uploadToS3 ? s3Bucket : undefined,
          }
          result = await exportApi.exportDailyCosts(request)
          break
        }

        case 'service_breakdown': {
          const request: CostExportRequest = {
            profile_name: profileName,
            start_date: startDate,
            end_date: endDate,
            export_format: selectedFormat as 'csv' | 'json',
            upload_to_s3: uploadToS3,
            s3_bucket: uploadToS3 ? s3Bucket : undefined,
          }
          result = await exportApi.exportServiceBreakdown(request)
          break
        }

        case 'rightsizing': {
          const request: RightSizingExportRequest = {
            profile_name: profileName,
            resource_types: resourceTypes,
            export_format: selectedFormat as 'csv' | 'json' | 'excel',
            upload_to_s3: uploadToS3,
            s3_bucket: uploadToS3 ? s3Bucket : undefined,
          }
          result = await exportApi.exportRightSizing(request)
          break
        }

        case 'unit_costs': {
          const request: UnitCostExportRequest = {
            profile_name: profileName,
            start_date: startDate,
            end_date: endDate,
            region: region || 'us-east-2',
            export_format: selectedFormat as 'csv' | 'json',
            upload_to_s3: uploadToS3,
            s3_bucket: uploadToS3 ? s3Bucket : undefined,
          }
          result = await exportApi.exportUnitCosts(request)
          break
        }

        case 'forecast': {
          result = await exportApi.exportForecast(
            profileName,
            startDate,
            endDate,
            forecastDays,
            selectedFormat as 'csv' | 'json',
            uploadToS3,
            uploadToS3 ? s3Bucket : undefined
          )
          break
        }

        case 'anomalies': {
          result = await exportApi.exportAnomalies(
            profileName,
            startDate,
            endDate,
            selectedFormat as 'csv' | 'json',
            uploadToS3,
            uploadToS3 ? s3Bucket : undefined
          )
          break
        }

        default:
          throw new Error('Invalid export type')
      }

      // Handle result
      if (uploadToS3 && typeof result === 'object' && 'success' in result) {
        // S3 upload response
        setExportStatus(result as ExportResponse)
      } else if (result instanceof Blob) {
        // File download
        const fileName = exportApi.generateExportFileName(exportType, profileName, selectedFormat)
        exportApi.downloadBlob(result, fileName)
        setExportStatus({
          success: true,
          message: `File downloaded successfully: ${fileName}`,
        })
      }
    } catch (error: any) {
      setExportStatus({
        success: false,
        message: error?.response?.data?.detail || error?.message || 'Export failed',
      })
    } finally {
      setIsExporting(false)
    }
  }

  const handleClose = () => {
    setExportStatus(null)
    setUploadToS3(false)
    setS3Bucket('')
    setSelectedFormat('csv')
    onClose()
  }

  return (
    <Transition appear show={isOpen} as={Fragment}>
      <Dialog as="div" className="relative z-50" onClose={handleClose}>
        <Transition.Child
          as={Fragment}
          enter="ease-out duration-300"
          enterFrom="opacity-0"
          enterTo="opacity-100"
          leave="ease-in duration-200"
          leaveFrom="opacity-100"
          leaveTo="opacity-0"
        >
          <div className="fixed inset-0 bg-black bg-opacity-25" />
        </Transition.Child>

        <div className="fixed inset-0 overflow-y-auto">
          <div className="flex min-h-full items-center justify-center p-4 text-center">
            <Transition.Child
              as={Fragment}
              enter="ease-out duration-300"
              enterFrom="opacity-0 scale-95"
              enterTo="opacity-100 scale-100"
              leave="ease-in duration-200"
              leaveFrom="opacity-100 scale-100"
              leaveTo="opacity-0 scale-95"
            >
              <Dialog.Panel className="w-full max-w-md transform overflow-hidden rounded-2xl bg-white p-6 text-left align-middle shadow-xl transition-all">
                <div className="flex items-center justify-between mb-4">
                  <Dialog.Title as="h3" className="text-lg font-bold text-gray-900">
                    {getExportTitle()}
                  </Dialog.Title>
                  <button
                    onClick={handleClose}
                    className="text-gray-400 hover:text-gray-600 transition-colors"
                  >
                    <X className="w-5 h-5" />
                  </button>
                </div>

                <div className="space-y-4">
                  {/* Format Selection */}
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      Export Format
                    </label>
                    <div className="grid grid-cols-2 gap-3">
                      {getAvailableFormats().includes('csv') && (
                        <button
                          onClick={() => setSelectedFormat('csv')}
                          className={`flex items-center justify-center gap-2 p-3 border rounded-lg transition-all ${
                            selectedFormat === 'csv'
                              ? 'border-primary-500 bg-primary-50 text-primary-700'
                              : 'border-gray-300 hover:border-gray-400'
                          }`}
                        >
                          <FileText className="w-5 h-5" />
                          <span className="font-medium">CSV</span>
                        </button>
                      )}

                      {getAvailableFormats().includes('json') && (
                        <button
                          onClick={() => setSelectedFormat('json')}
                          className={`flex items-center justify-center gap-2 p-3 border rounded-lg transition-all ${
                            selectedFormat === 'json'
                              ? 'border-primary-500 bg-primary-50 text-primary-700'
                              : 'border-gray-300 hover:border-gray-400'
                          }`}
                        >
                          <FileJson className="w-5 h-5" />
                          <span className="font-medium">JSON</span>
                        </button>
                      )}

                      {getAvailableFormats().includes('excel') && (
                        <button
                          onClick={() => setSelectedFormat('excel')}
                          className={`flex items-center justify-center gap-2 p-3 border rounded-lg transition-all ${
                            selectedFormat === 'excel'
                              ? 'border-primary-500 bg-primary-50 text-primary-700'
                              : 'border-gray-300 hover:border-gray-400'
                          }`}
                        >
                          <FileSpreadsheet className="w-5 h-5" />
                          <span className="font-medium">Excel</span>
                        </button>
                      )}
                    </div>
                  </div>

                  {/* S3 Upload Option */}
                  <div className="border-t pt-4">
                    <label className="flex items-center gap-2 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={uploadToS3}
                        onChange={(e) => setUploadToS3(e.target.checked)}
                        className="w-4 h-4 text-primary-600 border-gray-300 rounded focus:ring-primary-500"
                      />
                      <span className="text-sm font-medium text-gray-700">Upload to S3</span>
                    </label>

                    {uploadToS3 && (
                      <div className="mt-3">
                        <label htmlFor="s3-bucket" className="block text-sm font-medium text-gray-700 mb-1">
                          S3 Bucket Name
                        </label>
                        <input
                          type="text"
                          id="s3-bucket"
                          value={s3Bucket}
                          onChange={(e) => setS3Bucket(e.target.value)}
                          placeholder="my-reports-bucket"
                          className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500"
                        />
                      </div>
                    )}
                  </div>

                  {/* Export Status */}
                  {exportStatus && (
                    <div
                      className={`p-4 rounded-lg ${
                        exportStatus.success ? 'bg-green-50 border border-green-200' : 'bg-red-50 border border-red-200'
                      }`}
                    >
                      <div className="flex items-start gap-3">
                        {exportStatus.success ? (
                          <CheckCircle className="w-5 h-5 text-green-600 flex-shrink-0 mt-0.5" />
                        ) : (
                          <XCircle className="w-5 h-5 text-red-600 flex-shrink-0 mt-0.5" />
                        )}
                        <div className="flex-1">
                          <p
                            className={`text-sm font-medium ${
                              exportStatus.success ? 'text-green-900' : 'text-red-900'
                            }`}
                          >
                            {exportStatus.message}
                          </p>
                          {exportStatus.s3_url && (
                            <a
                              href={exportStatus.s3_url}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="text-sm text-primary-600 hover:text-primary-700 underline mt-1 inline-block"
                            >
                              View in S3
                            </a>
                          )}
                        </div>
                      </div>
                    </div>
                  )}

                  {/* Action Buttons */}
                  <div className="flex gap-3 pt-4 border-t">
                    <button
                      onClick={handleClose}
                      className="flex-1 px-4 py-2 border border-gray-300 rounded-lg text-gray-700 hover:bg-gray-50 font-medium transition-colors"
                    >
                      Cancel
                    </button>
                    <button
                      onClick={handleExport}
                      disabled={isExporting || (uploadToS3 && !s3Bucket)}
                      className="flex-1 px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
                    >
                      {isExporting ? (
                        <>
                          <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                          Exporting...
                        </>
                      ) : uploadToS3 ? (
                        <>
                          <Upload className="w-4 h-4" />
                          Upload
                        </>
                      ) : (
                        <>
                          <Download className="w-4 h-4" />
                          Download
                        </>
                      )}
                    </button>
                  </div>
                </div>
              </Dialog.Panel>
            </Transition.Child>
          </div>
        </div>
      </Dialog>
    </Transition>
  )
}
