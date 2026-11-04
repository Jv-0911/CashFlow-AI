/** Same-origin API transport. Sessions stay in HttpOnly cookies; no fixture fallback. */
export interface ApiResponse<T> { data: T; isDemo: boolean; status: number }
export class ApiError extends Error {
  status?: number;
  constructor(message: string, status?: number) { super(message); this.name='ApiError'; this.status=status; }
}
let csrf: string | null = null;
export interface Session { authenticated: boolean; read_only_demo: boolean; password_configured: boolean; payments_enabled: boolean; csrf_token: string | null }
export function validateMoney(value: unknown): void {
  if (!value || typeof value !== 'object') return;
  for (const [key, item] of Object.entries(value)) {
    if (key.endsWith('_cents') && item !== null && !Number.isSafeInteger(item)) throw new ApiError('Malformed financial response. Values have been hidden.');
    if (typeof item === 'object') validateMoney(item);
  }
}
export async function getSession(): Promise<Session> {
  const {data}=await apiClient<Session>('/api/v1/session');
  if (typeof data?.authenticated !== 'boolean' || typeof data.read_only_demo !== 'boolean' || (data.csrf_token !== null && typeof data.csrf_token !== 'string')) throw new ApiError('Invalid session response.');
  csrf=data.csrf_token;
  return data;
}
export async function apiClient<T>(endpoint: string, options: RequestInit = {}): Promise<ApiResponse<T>> {
  if (!endpoint.startsWith('/api/v1/') && endpoint !== '/health') throw new ApiError('Unsupported API destination.');
  const method=options.method ?? 'GET';
  if (method !== 'GET' && endpoint !== '/api/v1/session' && !csrf) await getSession();
  const controller=new AbortController();
  const timer=setTimeout(()=>controller.abort(),45000);
  try {
    const headers=new Headers(options.headers);
    if (options.body) headers.set('Content-Type','application/json');
    if (method !== 'GET' && csrf) headers.set('X-CSRF-Token',csrf);
    const response=await fetch(endpoint,{...options,headers,credentials:'same-origin',signal:controller.signal});
    const data=await response.json();
    if (!response.ok) throw new ApiError(typeof data?.error?.message==='string'?data.error.message:'The request could not be completed.',response.status);
    validateMoney(data);
    return {data:data as T,isDemo:response.headers.get('X-Demo-Data')==='true'||data?.is_demo===true||data?.is_demo_data===true,status:response.status};
  } catch(error) {
    if(error instanceof ApiError) throw error;
    throw new ApiError('Connection interrupted. Refresh the ledger before retrying any financial action.');
  } finally {clearTimeout(timer);}
}
