import { apiClient, type ApiResponse } from './client';
import type { HealthResponse } from '../types';

/**
 * Fetch application health status.
 */
export async function getHealth(): Promise<ApiResponse<HealthResponse>> {
  return apiClient<HealthResponse>('/api/v1/health');
}
