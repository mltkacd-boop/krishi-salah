import { useCallback, useEffect, useState } from 'react'

import { ApiError } from '../services/apiClient'
import { healthService } from '../services/healthService'
import type { ReadinessResponse } from '../types/api'

type Status = 'loading' | 'success' | 'error'

interface UseBackendHealthResult {
  status: Status
  data: ReadinessResponse | null
  error: string | null
  refetch: () => void
}

/**
 * Polls the real backend readiness endpoint. No success state is ever
 * assumed - `data` is only populated from an actual successful response,
 * and network/HTTP failures surface through `error` (Task 4 requirement:
 * no hardcoded success messages).
 */
export function useBackendHealth(): UseBackendHealthResult {
  const [status, setStatus] = useState<Status>('loading')
  const [data, setData] = useState<ReadinessResponse | null>(null)
  const [error, setError] = useState<string | null>(null)

  const fetchHealth = useCallback(() => {
    setStatus('loading')
    setError(null)
    healthService
      .getReadiness()
      .then((result) => {
        setData(result)
        setStatus('success')
      })
      .catch((err: unknown) => {
        const message = err instanceof ApiError ? err.message : 'Unknown error contacting backend.'
        setError(message)
        setData(null)
        setStatus('error')
      })
  }, [])

  useEffect(() => {
    fetchHealth()
  }, [fetchHealth])

  return { status, data, error, refetch: fetchHealth }
}
