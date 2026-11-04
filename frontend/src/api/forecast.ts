import { apiClient, ApiError, type ApiResponse } from './client.ts';
import type { ForecastResponse } from '../types/forecast.ts';
export function validateForecast(data: ForecastResponse): void {
  if (!data || data.currency !== 'USD' || !Array.isArray(data.days) || !data.days.length || data.days.length>30 || !Number.isSafeInteger(data.safety_reserve_cents)) throw new ApiError('Malformed forecast response.');
  for (const [i,d] of data.days.entries()) {
    if (!/^\d{4}-\d{2}-\d{2}$/.test(d.date) || [d.opening_balance_cents,d.receipts_cents,d.expenses_cents,d.closing_balance_cents].some(v=>!Number.isSafeInteger(v)) || d.closing_balance_cents!==d.opening_balance_cents+d.receipts_cents-d.expenses_cents || (i>0 && d.opening_balance_cents!==data.days[i-1].closing_balance_cents)) throw new ApiError('Malformed forecast balances.');
  }
}
export async function getForecast(): Promise<ApiResponse<ForecastResponse>> {
  const response=await apiClient<ForecastResponse>('/api/v1/forecast?horizon_days=30');
  validateForecast(response.data);
  return response;
}
