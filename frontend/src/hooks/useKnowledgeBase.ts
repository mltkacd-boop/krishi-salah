import { useCallback, useEffect, useState } from 'react'

import { ApiError } from '../services/apiClient'
import { knowledgeBaseService } from '../services/knowledgeBaseService'
import type { ApprovedUse, Crop, Source } from '../types/api'

type Status = 'loading' | 'success' | 'error'

interface UseKnowledgeBaseResult {
  status: Status
  crops: Crop[]
  sources: Source[]
  approvedUses: ApprovedUse[]
  error: string | null
  refetch: () => void
}

/**
 * Loads the real Phase 3 knowledge base (crops, sources, approved-use
 * records) from the backend. No data is hardcoded in the frontend - if the
 * backend is unreachable, `status` becomes 'error' and `error` carries the
 * real message, matching the no-fabricated-success-state pattern already
 * used by useBackendHealth.
 */
export function useKnowledgeBase(): UseKnowledgeBaseResult {
  const [status, setStatus] = useState<Status>('loading')
  const [crops, setCrops] = useState<Crop[]>([])
  const [sources, setSources] = useState<Source[]>([])
  const [approvedUses, setApprovedUses] = useState<ApprovedUse[]>([])
  const [error, setError] = useState<string | null>(null)

  const fetchAll = useCallback(() => {
    setStatus('loading')
    setError(null)
    Promise.all([
      knowledgeBaseService.getCrops(),
      knowledgeBaseService.getSources(),
      knowledgeBaseService.getApprovedUses(),
    ])
      .then(([cropsResult, sourcesResult, approvedUsesResult]) => {
        setCrops(cropsResult)
        setSources(sourcesResult)
        setApprovedUses(approvedUsesResult)
        setStatus('success')
      })
      .catch((err: unknown) => {
        const message = err instanceof ApiError ? err.message : 'Unknown error contacting backend.'
        setError(message)
        setStatus('error')
      })
  }, [])

  useEffect(() => {
    fetchAll()
  }, [fetchAll])

  return { status, crops, sources, approvedUses, error, refetch: fetchAll }
}
