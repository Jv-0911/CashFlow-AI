/**
 * Rescue types matching contracts/rescue-response.example.json.
 *
 * These represent AI-generated recovery recommendations.
 * All monetary impacts are in integer cents.
 */

export interface RescueAction {
  explanation?: string;
  backend_ranked?: boolean;
  impact_unquantified?: boolean;
  /** Unique identifier for this action */
  action_id: string;
  /** Human-readable title of the recommended action */
  title: string;
  /** Estimated financial impact in integer cents */
  estimated_impact_cents: number;
  /** List of assumptions underlying this recommendation */
  assumptions: string[];
  /** Model confidence score in feasibility and outcome certainty */
  confidence?: 'high' | 'medium' | 'low';
  /** Grounded analytical rationale for why this action is recommended */
  rationale?: string;
  /** Day offset from the simulation start or breach date when cash impact manifests */
  timing_days_offset?: number;
  /** Category of liquidity intervention */
  category?: 'receivables' | 'disbursements' | 'financing';
  /** Grounded evidence transaction IDs specific to this recommendation, if available */
  evidence_ids?: string[];
}

export interface RescueResponse {
  source?: 'ai' | 'deterministic';
  integration_warnings?: string[];
  /** Summary of the detected cash shortage or risk */
  summary: string;
  /** Risk level assessment */
  risk_level: 'high' | 'medium' | 'low' | 'unknown';
  /** Transaction IDs used as evidence for this analysis */
  evidence_ids: string[];
  /** Ranked list of recovery actions */
  recommended_actions: RescueAction[];
  /** Explicit flag indicating this response is demo fixture data */
  is_demo?: boolean;
  /** Notice confirming whether data is from fixture or live calculation */
  disclaimer?: string;
  /** Flag indicating backend API was unreachable and local fallback was used */
  backend_unavailable?: boolean;
}
