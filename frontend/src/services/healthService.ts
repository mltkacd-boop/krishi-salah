import { apiClient } from './apiClient'
import type { LivenessResponse, ReadinessResponse } from '../types/api'

export const healthService = {
  getLiveness: () => apiClient.get<LivenessResponse>('/health'),
  getReadiness: () => apiClient.get<ReadinessResponse>('/health/ready'),
}
