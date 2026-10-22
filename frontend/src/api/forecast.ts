import { apiClient, type ApiResponse } from './client';
import type { ForecastResponse } from '../types';
import { DEMO_FORECAST } from '../data/demo-fixtures';

/**
 * Fetch cash-flow forecast.
 * Gracefully falls back to local demo fixture if the backend is not reachable.
 */
export async function getForecast(): Promise<ApiResponse<ForecastResponse>> {
  try {
    return await apiClient<ForecastResponse>('/api/v1/forecast');
  } catch (error) {
    console.warn('Backend unavailable, falling back to demo forecast fixture:', error);
    return {
      data: DEMO_FORECAST,
      isDemo: true,
      status: 200,
    };
  }
}
