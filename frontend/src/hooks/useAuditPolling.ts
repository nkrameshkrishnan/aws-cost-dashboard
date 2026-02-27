/**
 * Hook for polling async audit job status and results.
 */
import { useState, useEffect, useCallback, useRef } from 'react'
import { finopsApi, AuditJobStatus } from '@/api/finops'
import type { FullAuditResults } from '@/types/audit'

interface UseAuditPollingOptions {
  jobId: string | null
  interval?: number  // Polling interval in ms (default: 2000)
  onComplete?: (results: FullAuditResults) => void
  onError?: (error: string) => void
  onProgress?: (status: AuditJobStatus) => void
}

interface UseAuditPollingReturn {
  status: AuditJobStatus | null
  results: FullAuditResults | null
  isPolling: boolean
  error: string | null
  stopPolling: () => void
  restartPolling: () => void
}

export function useAuditPolling({
  jobId,
  interval = 2000,
  onComplete,
  onError,
  onProgress
}: UseAuditPollingOptions): UseAuditPollingReturn {
  const [status, setStatus] = useState<AuditJobStatus | null>(null)
  const [results, setResults] = useState<FullAuditResults | null>(null)
  const [isPolling, setIsPolling] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const intervalRef = useRef<NodeJS.Timeout | null>(null)

  // Use refs for callbacks to avoid stale closures
  const onCompleteRef = useRef(onComplete)
  const onErrorRef = useRef(onError)
  const onProgressRef = useRef(onProgress)

  useEffect(() => {
    onCompleteRef.current = onComplete
    onErrorRef.current = onError
    onProgressRef.current = onProgress
  }, [onComplete, onError, onProgress])

  const stopPolling = useCallback(() => {
    if (intervalRef.current) {
      clearInterval(intervalRef.current)
      intervalRef.current = null
    }
    setIsPolling(false)
  }, [])

  const pollStatus = useCallback(async () => {
    if (!jobId) {
      console.log('pollStatus: no jobId')
      return
    }

    console.log('pollStatus: fetching status for job', jobId)

    try {
      const jobStatus = await finopsApi.getAuditStatus(jobId)

      console.log('pollStatus: received status', jobStatus)
      console.log('pollStatus: calling setStatus with', jobStatus)
      setStatus(jobStatus)

      // Try to fetch partial or final results
      if (jobStatus.status === 'running' || jobStatus.status === 'completed') {
        try {
          const partialResults = await finopsApi.getAuditResults(jobId, true)
          setResults(partialResults)
          // Pass results through status to onProgress callback
          onProgressRef.current?.({ ...jobStatus, results: partialResults })
        } catch (err: any) {
          // Partial results not available yet, just notify progress with status
          onProgressRef.current?.(jobStatus)
        }
      } else {
        // Notify progress callback using ref
        onProgressRef.current?.(jobStatus)
      }

      // Check if complete
      if (jobStatus.status === 'completed') {
        stopPolling()
        // Results already fetched above, call onComplete if we have them
        if (results) {
          onCompleteRef.current?.(results)
        } else {
          // Fallback: fetch results one more time
          try {
            const finalResults = await finopsApi.getAuditResults(jobId, true)
            setResults(finalResults)
            onCompleteRef.current?.(finalResults)
          } catch (err: any) {
            setError(err.response?.data?.detail || 'Failed to get results')
            onErrorRef.current?.(err.response?.data?.detail || 'Failed to get results')
          }
        }
      } else if (jobStatus.status === 'failed') {
        stopPolling()
        const errorMsg = jobStatus.error || 'Audit job failed'
        setError(errorMsg)
        onErrorRef.current?.(errorMsg)
      }
    } catch (err: any) {
      // If job not found or other error, stop polling
      const errorMsg = err.response?.data?.detail || 'Failed to get job status'
      setError(errorMsg)
      onErrorRef.current?.(errorMsg)
      stopPolling()
    }
  }, [jobId, stopPolling, results])

  const restartPolling = useCallback(() => {
    if (!jobId) return

    stopPolling()
    setError(null)
    setResults(null)
    setIsPolling(true)

    // Poll immediately
    pollStatus()

    // Start interval
    intervalRef.current = setInterval(pollStatus, interval)
  }, [jobId, stopPolling, pollStatus, interval])

  // Start polling when jobId changes
  useEffect(() => {
    if (jobId) {
      // Inline the polling start logic to avoid dependency issues
      stopPolling()
      setError(null)
      setResults(null)
      setIsPolling(true)

      // Poll immediately
      pollStatus()

      // Start interval
      intervalRef.current = setInterval(pollStatus, interval)
    }

    return () => {
      stopPolling()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [jobId, interval])

  return {
    status,
    results,
    isPolling,
    error,
    stopPolling,
    restartPolling
  }
}
