import type { ClassifyResponse, ModelInfoResponse } from '../types/api'
import { apiClient } from './apiClient'

/**
 * Phase 4 (Module B) — query classification.
 *
 * The backend returns an interpretation of what the user asked about (crop,
 * task, safety topic) with a status per dimension. Callers must treat this as
 * routing information only: it is never a recommendation and never contains a
 * dose, PHI, REI or PPE value.
 */
export const classificationService = {
  classify(query: string): Promise<ClassifyResponse> {
    return apiClient.post<ClassifyResponse>('/classification/classify', { query })
  },
  /** Evaluation only: the model card, not a per-question answer. */
  modelInfo: () => apiClient.get<ModelInfoResponse>('/classification/model-info'),
}
