/**
 * Typed HTTP client for CashFlow AI backend API.
 * Supports configurable baseUrl, error normalization, and X-Demo-Data header detection.
 */

export interface ApiResponse<T> {
  data: T;
  isDemo: boolean;
  status: number;
}

export class ApiError extends Error {
  status?: number;
  details?: unknown;

  constructor(message: string, status?: number, details?: unknown) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.details = details;
  }
}

const BASE_URL = import.meta.env.VITE_API_URL || '';

export async function apiClient<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<ApiResponse<T>> {
  const url = endpoint.startsWith('http') ? endpoint : `${BASE_URL}${endpoint}`;

  try {
    const response = await fetch(url, {
      headers: {
        'Content-Type': 'application/json',
        ...options.headers,
      },
      ...options,
    });

    const isDemo = response.headers.get('X-Demo-Data') === 'true';

    if (!response.ok) {
      let errorDetails: unknown = null;
      try {
        errorDetails = await response.json();
      } catch {
        // non-JSON error
      }
      throw new ApiError(
        `Request failed with status ${response.status}`,
        response.status,
        errorDetails
      );
    }

    const data = (await response.json()) as T;
    return { data, isDemo, status: response.status };
  } catch (err: unknown) {
    if (err instanceof ApiError) {
      throw err;
    }
    const message = err instanceof Error ? err.message : 'Unknown network error';
    throw new ApiError(message);
  }
}
