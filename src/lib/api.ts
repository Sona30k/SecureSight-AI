import axios, { AxiosError, InternalAxiosRequestConfig } from 'axios'

export type Role = 'citizen' | 'police' | 'bank' | 'telecom_provider' | 'administrator'
export type User = { id:string; email:string; full_name:string; role:Role; is_active:boolean; created_at:string }
export type TokenPair = { access_token:string; refresh_token:string; token_type:string; expires_in:number }
export type Prediction = { prediction:string; confidence:number; risk_score:number; explanation:string[]; model_version:string; details:Record<string, unknown> }
export type Report = { id:string; title:string; description:string; category:string; location?:string; status:string; risk_score:number; money_involved:number; created_at:string }
export type DashboardData = {
  today_frauds:number; counterfeit_detected:number; money_saved:number; active_investigations:number;
  protected_citizens:number; high_risk_calls:number; digital_arrest_cases:number;
  monthly_trends:{date:string;count:number}[]; district_rankings:{district:string;incidents:number}[];
  risk_distribution:Record<'low'|'medium'|'high'|'critical',number>; recent_reports:Report[];
}

const TOKEN_KEY = 'sentinelx_tokens'
const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

export const tokenStore = {
  get: ():TokenPair|null => {
    try { return JSON.parse(localStorage.getItem(TOKEN_KEY) || 'null') }
    catch { return null }
  },
  set: (tokens:TokenPair) => localStorage.setItem(TOKEN_KEY, JSON.stringify(tokens)),
  clear: () => localStorage.removeItem(TOKEN_KEY),
}

export const api = axios.create({ baseURL: API_URL, timeout: 15_000 })

api.interceptors.request.use((config:InternalAxiosRequestConfig) => {
  const token = tokenStore.get()?.access_token
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

let refreshRequest:Promise<TokenPair>|null = null
api.interceptors.response.use(
  response => response,
  async (error:AxiosError) => {
    const config = error.config as (InternalAxiosRequestConfig & { _retry?:boolean; _attempt?:number })|undefined
    if (!config) return Promise.reject(error)
    if (error.response?.status === 401 && !config._retry && tokenStore.get()?.refresh_token) {
      config._retry = true
      refreshRequest ||= axios.post<TokenPair>(`${API_URL}/auth/refresh`, { refresh_token:tokenStore.get()!.refresh_token })
        .then(result => { tokenStore.set(result.data); return result.data })
        .finally(() => { refreshRequest = null })
      try {
        const tokens = await refreshRequest
        config.headers.Authorization = `Bearer ${tokens.access_token}`
        return api(config)
      } catch {
        tokenStore.clear()
        window.dispatchEvent(new Event('sentinelx:logout'))
      }
    }
    const retryable = !error.response || error.response.status >= 500
    config._attempt = config._attempt || 0
    if (retryable && config.method === 'get' && config._attempt < 2) {
      config._attempt += 1
      await new Promise(resolve => setTimeout(resolve, 350 * 2 ** config._attempt!))
      return api(config)
    }
    return Promise.reject(error)
  },
)

export const errorMessage = (error:unknown) => {
  if (axios.isAxiosError(error)) {
    const detail = error.response?.data?.detail || error.response?.data?.message
    return typeof detail === 'string' ? detail : 'The SentinelX service is temporarily unavailable.'
  }
  return error instanceof Error ? error.message : 'Something went wrong.'
}

export const services = {
  auth: {
    login: async (email:string,password:string) => {
      const {data} = await api.post<TokenPair>('/auth/login',{email,password})
      tokenStore.set(data)
      return data
    },
    me: async () => (await api.get<User>('/auth/me')).data,
    updateMe: async (full_name:string) => (await api.patch<User>('/auth/me',{full_name})).data,
    logout: async () => { try { await api.post('/auth/logout') } finally { tokenStore.clear() } },
  },
  analytics: () => api.get<DashboardData>('/analytics/dashboard').then(r=>r.data),
  reports: (params?:Record<string,unknown>) => api.get<{items:Report[];total:number}>('/reports',{params}).then(r=>r.data),
  scam: (payload:Record<string,unknown>) => api.post<Prediction & {case_id?:string;scam_probability?:number;detected_keywords?:string[]}>('/ai/scam-detection',payload).then(r=>r.data),
  currency: (file:File) => {
    const form = new FormData(); form.append('image',file)
    return api.post<Prediction>('/ai/currency-detection',form).then(r=>r.data)
  },
  graph: () => api.get('/ai/fraud-network').then(r=>r.data),
  hotspots: () => api.get('/ai/hotspots').then(r=>r.data),
  heatmap: (params?:Record<string,unknown>) => api.get('/crime/heatmap',{params}).then(r=>r.data),
  chat: (text:string) => {
    const form = new FormData(); form.append('text',text)
    return api.post('/assistant/chat',form).then(r=>r.data)
  },
}

export const websocketUrl = (channel:string) => {
  const token = tokenStore.get()?.access_token || ''
  return `${API_URL.replace(/^http/,'ws')}/ws/${channel}?token=${encodeURIComponent(token)}`
}
