/**
 * Rescue types matching contracts/rescue-response.example.json.
 *
 * These represent AI-generated recovery recommendations.
 * All monetary impacts are in integer cents.
 */

export interface RescueAction {
  /** Unique identifier for this action */
  action_id: string;
  /** Human-readable title of the recommended action */
  title: string;
  /** Estimated financial impact in integer cents */
  estimated_impact_cents: number;
  /** List of assumptions underlying this recommendation */
  assumptions: string[];
}

export interface RescueResponse {
  /** Summary of the detected cash shortage or risk */
  summary: string;
  /** Risk level assessment */
  risk_level: 'high' | 'medium' | 'low';
  /** Transaction IDs used as evidence for this analysis */
  evidence_ids: string[];
  /** Ranked list of recovery actions */
  recommended_actions: RescueAction[];
}
