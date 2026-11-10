import { apiClient } from './apiClient'
import type { ApprovedUse, Crop, KnowledgeBaseStatusResponse, Source } from '../types/api'

/**
 * Phase 3 Knowledge Base (Module C) service. All calls hit the real backend
 * /knowledge-base/* endpoints - no mocked/hardcoded data.
 */
export const knowledgeBaseService = {
  getCrops: () => apiClient.get<Crop[]>('/knowledge-base/crops'),
  getSources: () => apiClient.get<Source[]>('/knowledge-base/sources'),
  getApprovedUses: (cropId?: string) =>
    apiClient.get<ApprovedUse[]>(
      cropId ? `/knowledge-base/approved-uses?crop_id=${encodeURIComponent(cropId)}` : '/knowledge-base/approved-uses',
    ),
  /** Evaluation only: which storage backend is actually serving the records. */
  status: () => apiClient.get<KnowledgeBaseStatusResponse>('/knowledge-base/status'),
}
