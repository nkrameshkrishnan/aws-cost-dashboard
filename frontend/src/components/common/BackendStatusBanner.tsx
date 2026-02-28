import { useEffect, useState } from 'react'
import { AlertCircle, X } from 'lucide-react'
import axios from 'axios'

export function BackendStatusBanner() {
  const [isHealthy, setIsHealthy] = useState<boolean | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [isDismissed, setIsDismissed] = useState(false)

  useEffect(() => {
    checkApiHealth()
  }, [])

  async function checkApiHealth() {
    try {
      const apiBaseUrl = import.meta.env.VITE_API_BASE_URL
      const apiVersion = import.meta.env.VITE_API_VERSION || 'v1'

      if (!apiBaseUrl || apiBaseUrl.includes('api-id.execute-api')) {
        throw new Error('API Gateway URL not configured')
      }

      const response = await axios.get(`${apiBaseUrl}/api/${apiVersion}/health/status`, {
        timeout: 5000,
        validateStatus: (status) => status < 500,
      })

      if (response.status === 200) {
        setIsHealthy(true)
      } else {
        throw new Error(`Backend returned status ${response.status}`)
      }
    } catch (err) {
      if (axios.isAxiosError(err)) {
        if (err.code === 'ECONNABORTED') {
          setError('Connection timeout - backend is not responding')
        } else if (err.code === 'ERR_NETWORK') {
          setError('Network error - cannot reach backend')
        } else if (err.response) {
          setError(`Backend error: ${err.response.status}`)
        } else if (err.request) {
          setError('No response from backend - check if API Gateway is deployed')
        } else {
          setError(err.message)
        }
      } else if (err instanceof Error) {
        setError(err.message)
      } else {
        setError('Unknown error occurred')
      }
      setIsHealthy(false)
    }
  }

  if (isHealthy || isDismissed) {
    return null
  }

  return (
    <div className="bg-amber-50 border-b border-amber-200">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3 flex-1">
            <AlertCircle className="h-5 w-5 text-amber-600 flex-shrink-0" />
            <div className="flex-1">
              <p className="text-sm font-medium text-amber-900">
                Backend Not Configured
              </p>
              <p className="text-sm text-amber-700">
                {error || 'The AWS Cost Dashboard backend is not reachable. Deploy the infrastructure to enable full functionality.'}
              </p>
            </div>
          </div>
          <button
            onClick={() => setIsDismissed(true)}
            className="ml-4 inline-flex text-amber-600 hover:text-amber-800 focus:outline-none"
            aria-label="Dismiss"
          >
            <X className="h-5 w-5" />
          </button>
        </div>
      </div>
    </div>
  )
}
