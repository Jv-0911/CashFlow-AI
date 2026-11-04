import { apiClient, type ApiResponse } from './client.ts';
import { validateForecast } from './forecast.ts';
import type { ScenarioRequest, ScenarioResponse, ScenarioModifiers } from '../types/scenario.ts';
import type { ForecastResponse } from '../types/forecast.ts';
export async function simulateScenario(request: ScenarioRequest, modifiers: ScenarioModifiers, _baselineForecast?: ForecastResponse | null): Promise<ApiResponse<ScenarioResponse>> {
  const response=await apiClient<ScenarioResponse>('/api/v1/scenario',{method:'POST',body:JSON.stringify({...request,modifiers})});
  validateForecast({...response.data,is_demo:true,disclaimer:response.data.disclaimer??''});
  if(!response.data.comparison||!Array.isArray(response.data.comparison.changes_applied)) throw new Error('Malformed scenario comparison.');
  return response;
}
