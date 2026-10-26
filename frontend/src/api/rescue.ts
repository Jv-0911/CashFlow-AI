import { apiClient, type ApiResponse } from './client';
import type { RescueResponse } from '../types';
import { DEMO_RESCUE } from '../data/demo-fixtures';

/**
 * Fetch AI Rescue recommendations.
 *
 * Calls /api/v1/rescue. If the backend is unreachable or not yet implemented,
 * gracefully falls back to the contract-conforming demo fixture while explicitly
 * flagging `backend_unavailable: true` and `isDemo: true` so the UI can display
 * a persistent, visible notice with retry capability.
 */
export async function getRescue(): Promise<ApiResponse<RescueResponse>> {
  try {
    const response = await apiClient<RescueResponse>('/api/v1/rescue');
    return response;
  } catch (error) {
    console.warn(
      'AI Rescue endpoint (/api/v1/rescue) unavailable, falling back to grounded demo fixture:',
      error
    );
    return {
      data: {
        ...DEMO_RESCUE,
        is_demo: true,
        backend_unavailable: true,
        disclaimer:
          'DEMO FIXTURE: Backend AI Rescue endpoint (/api/v1/rescue) is currently unavailable. Displaying local grounded fixture conforming to contracts/rescue-response.example.json.',
      },
      isDemo: true,
      status: 200,
    };
  }
}
