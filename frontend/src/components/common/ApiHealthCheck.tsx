import { useEffect, useState, ReactNode } from 'react'
import axios from 'axios'
import { SetupRequired } from './SetupRequired'
import { LoadingPage } from './LoadingPage'

interface ApiHealthCheckProps {
  children: ReactNode
}

export function ApiHealthCheck({ children }: ApiHealthCheckProps) {
  const [isHealthy, setIsHealthy] = useState<boolean | null>(null)
  const [error, setError] = useState<Error | null>(null)
  const [isChecking, setIsChecking] = useState(true)

  useEffect(() => {
    checkApiHealth()
  }, [])

  const checkApiHealth = async () => {
    setIsChecking(true)
    setError(null)

    try {
      const apiBaseUrl = import.meta.env.VITE_API_BASE_URL
      const apiVersion = import.meta.env.VITE_API_VERSION || 'v1'

      // Check if API URL is configured
      if (!apiBaseUrl || apiBaseUrl.includes('api-id.execute-api')) {
        throw new Error(
          'API Gateway URL not configured. Please update VITE_API_BASE_URL in .env.production'
        )
      }

      // Try to reach the health endpoint with a timeout
      const response = await axios.get(`${apiBaseUrl}/api/${apiVersion}/health`, {
        timeout: 5000,
        validateStatus: (status) => status < 500, // Accept any non-500 status
      })

      if (response.status === 200) {
        setIsHealthy(true)
      } else {
        throw new Error(`Backend returned status ${response.status}`)
      }
    } catch (err) {
      console.error('API health check failed:', err)

      if (axios.isAxiosError(err)) {
        if (err.code === 'ECONNABORTED') {
          setError(new Error('Connection timeout - backend is not responding'))
        } else if (err.code === 'ERR_NETWORK') {
          setError(new Error('Network error - cannot reach backend'))
        } else if (err.response) {
          setError(new Error(`Backend error: ${err.response.status} ${err.response.statusText}`))
        } else if (err.request) {
          setError(new Error('No response from backend - check if API Gateway is deployed'))
        } else {
          setError(new Error(err.message))
        }
      } else if (err instanceof Error) {
        setError(err)
      } else {
        setError(new Error('Unknown error occurred'))
      }

      setIsHealthy(false)
    } finally {
      setIsChecking(false)
    }
  }

  if (isChecking) {
    return <LoadingPage message="Connecting to backend..." />
  }

  if (!isHealthy) {
    return <SetupRequired error={error || undefined} type="backend" />
  }

  return <>{children}</>
}
