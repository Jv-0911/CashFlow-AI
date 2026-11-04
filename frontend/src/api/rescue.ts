import { apiClient, ApiError, type ApiResponse } from './client.ts';
import type { RescueResponse } from '../types/rescue.ts';
export async function getRescue(): Promise<ApiResponse<RescueResponse>> {
  const response=await apiClient<RescueResponse>('/api/v1/rescue/analyze?horizon_days=30',{method:'POST'});
  const data=response.data;
  if (!data || !Array.isArray(data.recommended_actions) || !Array.isArray(data.evidence_ids) || typeof data.summary!=='string' || !['low','medium','high','unknown'].includes(data.risk_level)) throw new ApiError('Malformed rescue response.');
  data.recommended_actions=data.recommended_actions.map(a=>{
    if(typeof a.action_id!=='string'||!Array.isArray(a.assumptions)||!Array.isArray(a.evidence_ids)) throw new ApiError('Malformed rescue action.');
    return {...a,rationale:a.explanation,estimated_impact_cents:a.estimated_impact_cents??0,impact_unquantified:a.estimated_impact_cents===null,backend_ranked:true};
  });
  data.disclaimer='Recommendations are estimates, not additional received cash. '+(data.source==='ai'?'AI-assisted ranking.':'Deterministic analysis; no external AI result.')+' '+(data.integration_warnings??[]).join(' ');
  return response;
}
