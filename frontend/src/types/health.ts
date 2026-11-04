/**
 * Health check types matching backend/app/api/schemas.py (HealthResponse).
 */

export interface HealthResponse {
  /** Application health status, e.g. "ok" */
  status: string;
  /** API semantic version string, e.g. "0.1.0" */
  version: string;
}
