import type { AdvisoryResponse, RagStatusResponse, RulesStatusResponse } from '../types/api'
import { apiClient } from './apiClient'

export interface AskOptions {
  /** Omit to let the backend follow the language of the question. */
  language?: 'en' | 'hi'
}

/**
 * Phase 6/7 advisory service.
 *
 * The request carries only what the backend accepts: a question, an optional
 * interface language and the evidence cap. No decision, status or safety field
 * is ever sent — the backend rejects unknown fields, and the UI has no business
 * asserting any of them.
 */
export const advisoryService = {
  ask(query: string, options: AskOptions = {}): Promise<AdvisoryResponse> {
    const body: Record<string, unknown> = { query, max_evidence: 5 }
    if (options.language) body.language = options.language
    return apiClient.post<AdvisoryResponse>('/rag/answer', body)
  },
  status: () => apiClient.get<RagStatusResponse>('/rag/status'),
  rulesStatus: () => apiClient.get<RulesStatusResponse>('/rules/status'),
}
