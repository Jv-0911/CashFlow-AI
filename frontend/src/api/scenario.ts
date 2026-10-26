import { apiClient, type ApiResponse } from './client.ts';
import type { ScenarioRequest, ScenarioResponse, ScenarioModifiers } from '../types/scenario.ts';
import type { ForecastResponse } from '../types/forecast.ts';
import { calculateScenarioProjection } from '../features/scenarios/scenario-math.ts';

/**
 * Executes a what-if scenario simulation.
 *
 * 1. Attempts to call backend endpoint POST /api/v1/scenario.
 * 2. If the backend is unreachable or not implemented, falls back to the client-side
 *    deterministic scenario math engine utilizing the baseline forecast, explicitly
 *    flagging `backend_unavailable: true` and `is_demo: true` so the UI presents
 *    a visible notice with retry capability.
 */
export async function simulateScenario(
  request: ScenarioRequest,
  modifiers: ScenarioModifiers,
  baselineForecast?: ForecastResponse | null
): Promise<ApiResponse<ScenarioResponse>> {
  try {
    const response = await apiClient<ScenarioResponse>('/api/v1/scenario', {
      method: 'POST',
      body: JSON.stringify({
        ...request,
        modifiers,
      }),
    });
    return response;
  } catch (error) {
    console.warn(
      'Backend scenario endpoint (/api/v1/scenario) unavailable. Utilizing grounded local calculation model:',
      error
    );

    if (!baselineForecast || !baselineForecast.days || baselineForecast.days.length === 0) {
      throw new Error(
        'Baseline forecast data is unavailable. Cannot compute scenario simulation without active baseline.'
      );
    }

    const calculated = calculateScenarioProjection(
      baselineForecast.days,
      request.safety_reserve_cents,
      modifiers,
      request.currency
    );

    const scenarioResponse: ScenarioResponse = {
      currency: request.currency,
      safety_reserve_cents: request.safety_reserve_cents,
      first_reserve_breach_date: calculated.first_reserve_breach_date,
      days: calculated.days,
      comparison: calculated.comparison,
      is_demo: true,
      backend_unavailable: true,
      disclaimer: calculated.disclaimer,
    };

    return {
      data: scenarioResponse,
      isDemo: true,
      status: 200,
    };
  }
}
