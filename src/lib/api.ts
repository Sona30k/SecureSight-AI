import axios, { AxiosError, InternalAxiosRequestConfig } from 'axios'

export type Role = 'citizen' | 'police' | 'bank' | 'telecom_provider' | 'administrator'
export type AccountStatus = 'pending' | 'verified' | 'rejected' | 'blocked'
export type User = {
  id:string; email:string; full_name:string; phone:string|null; role:Role;
  account_status:AccountStatus; is_active:boolean; email_verified:boolean; phone_verified:boolean;
  state:string|null; district:string|null; preferred_language:string;
  organization:string|null; employee_id:string|null; badge_number:string|null;
  police_station:string|null; department:string|null; rank:string|null; branch:string|null;
  profile_picture:string|null; notification_preferences:Record<string,boolean>;
  created_at:string; last_login_at:string|null;
  demo_verification_token?:string|null;demo_otp?:string|null;
}
export type TokenPair = { access_token:string; refresh_token:string; token_type:string; expires_in:number; session_id?:string }
export type UserSession = {id:string;ip_address:string|null;user_agent:string|null;device_name:string|null;remember_me:boolean;last_seen_at:string;expires_at:string;revoked_at:string|null}
export type RegisterPayload = {
  email:string;full_name:string;phone?:string;password:string;confirm_password:string;role:Role;
  state?:string;district?:string;preferred_language?:string;organization?:string;
  employee_id?:string;badge_number?:string;police_station?:string;department?:string;rank?:string;branch?:string;
  accept_terms:boolean;
}
export type Prediction = { prediction:string; confidence:number; risk_score:number; explanation:string[]; model_version:string; details:Record<string, unknown> }
export type AssistantProvider = 'auto'|'openai'|'gemini'|'llama'|'rules'
export type AssistantReply = {
  response:string; confidence:number; risk_level:'low'|'medium'|'high'|'critical';
  recommendations:string[]; analysis_id:string; provider:string; model:string;
  provider_status:'live'|'fallback'|'local'; grounded_context:string[]; language:string;
}
export type AssistantProviderInfo = {id:Exclude<AssistantProvider,'auto'>;label:string;model:string;configured:boolean}
export type ThreatLevel = 'low'|'medium'|'high'|'critical'
export type ConversationStage = { stage:string; evidence:string; severity:'low'|'medium'|'high'; order:number }
export type TelecomSignals = {
  network_asserted_number?:string;attestation?:'verified'|'partial'|'failed'|'unavailable';
  network_type?:'mobile'|'landline'|'voip'|'international'|'unknown';
  origination_country?:string;sim_age_days?:number;recent_sim_swap?:boolean;
  diversion_count?:number;carrier_risk_score?:number;provider_reference?:string;
}
export type DigitalArrestResult = {
  case_id:string; risk_score:number; confidence:number; scam_probability:number; threat_level:ThreatLevel;
  detected_keywords:string[]; spoof_detected:boolean; recommendation:string; explanation:string[];
  manipulation_techniques:string[]; psychological_signals:Record<string,number>;
  authority_impersonation:string[]; financial_threats:string[]; conversation_stages:ConversationStage[];
  suspicious_spans:{start:number;end:number;text:string;category:string;severity:'green'|'yellow'|'red'}[];
  caller_reputation:{caller_number:string;report_count:number;average_risk:number;reputation_score:number;total_victims:number;last_seen?:string;label:string};
  signals:Record<string,number>; model_version:string;
  spoof_score:number;spoof_reasons:string[];voice_forensics?:Record<string,unknown>|null;
  external_actions:{integration:string;action:string;status:string}[];
}
export type DigitalArrestHistory = {
  id:string;caller_number:string;duration:number;country?:string;caller_location?:string;risk_score:number;
  confidence:number;scam_probability:number;threat_level:ThreatLevel;spoof_detected:boolean;
  detected_keywords:string[];status:string;blocked:boolean;police_notified:boolean;report_saved:boolean;created_at:string;
}
export type DigitalArrestDashboard = {
  today_scam_calls:number;blocked_calls:number;average_risk:number;high_risk_numbers:number;total_cases:number;
  risk_distribution:Record<ThreatLevel,number>;common_keywords:{keyword:string;count:number}[];
  top_numbers:{caller_number:string;reports:number;average_risk:number;reputation_score:number}[];
  daily_cases:{date:string;count:number}[];
}
export type CurrencyFeature = {detected:boolean;confidence:number;status:'PASS'|'FAIL'|'NOT ASSESSED';value?:string|null;valid?:boolean;ocr_available?:boolean}
export type CurrencyResult = {
  case_id:string;prediction:'Genuine'|'Likely Genuine'|'Suspicious'|'Counterfeit';
  confidence:number;authenticity_score:number;counterfeit_probability:number;
  denomination?:string;series:string;legal_tender:boolean;currency_status:string;specimen_detected:boolean;
  serial_number?:string;serial_valid:boolean;serial_duplicate:boolean;
  security_thread:boolean;watermark:boolean;features:Record<string,CurrencyFeature>;
  quality:Record<string,string|number|boolean>;bounding_box:{x:number;y:number;width:number;height:number};
  detected_note:string;heatmap:string;explanation:string[];model_version:string;explainability_method:string;
  spectral_analysis:Record<string,any>;model_provenance:Record<string,any>;
}
export type CurrencyHistory = {id:string;prediction:string;confidence:number;authenticity_score:number;counterfeit_probability:number;denomination?:string;series?:string;legal_tender:boolean;currency_status?:string;serial_number?:string;serial_duplicate:boolean;location?:string;created_at:string}
export type CurrencyStatistics = {total_notes_scanned:number;fake_notes_found:number;detection_accuracy:number|null;most_counterfeited_denomination:string|null;denomination_distribution:{denomination:string;count:number}[];monthly_trends:{month:string;count:number}[]}
export type Report = { id:string; title:string; description:string; category:string; location?:string; status:string; risk_score:number; money_involved:number; created_at:string }
export type NotificationItem = {
  id:string; channel:'sms'|'email'|'push'|'whatsapp'; subject:string; body:string;
  status:string; created_at:string; read:boolean;
}
export type DashboardData = {
  today_frauds:number; counterfeit_detected:number; money_saved:number; active_investigations:number;
  protected_citizens:number; high_risk_calls:number; digital_arrest_cases:number;
  monthly_trends:{date:string;count:number}[]; district_rankings:{district:string;incidents:number}[];
  risk_distribution:Record<'low'|'medium'|'high'|'critical',number>; recent_reports:Report[];
}

const TOKEN_KEY = 'shieldiq_tokens'
const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

export const tokenStore = {
  get: ():TokenPair|null => {
    try { return JSON.parse(localStorage.getItem(TOKEN_KEY) || 'null') }
    catch { return null }
  },
  set: (tokens:TokenPair) => localStorage.setItem(TOKEN_KEY, JSON.stringify(tokens)),
  clear: () => localStorage.removeItem(TOKEN_KEY),
}

export const api = axios.create({ baseURL: API_URL, timeout: 15_000, withCredentials:true })

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
      refreshRequest ||= axios.post<TokenPair>(`${API_URL}/auth/refresh`, { refresh_token:tokenStore.get()!.refresh_token }, {withCredentials:true})
        .then(result => { tokenStore.set(result.data); return result.data })
        .finally(() => { refreshRequest = null })
      try {
        const tokens = await refreshRequest
        config.headers.Authorization = `Bearer ${tokens.access_token}`
        return api(config)
      } catch {
        tokenStore.clear()
        window.dispatchEvent(new Event('shieldiq:logout'))
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
    return typeof detail === 'string' ? detail : 'The ShieldIQ service is temporarily unavailable.'
  }
  return error instanceof Error ? error.message : 'Something went wrong.'
}

export const services = {
  auth: {
    login: async (email:string,password:string,remember_me=false) => {
      const {data} = await api.post<TokenPair>('/auth/login',{email,password,remember_me})
      tokenStore.set(data)
      return data
    },
    register: (payload:RegisterPayload) => api.post<User>('/auth/register',payload).then(r=>r.data),
    verifyEmail: (token:string) => api.post<{message:string}>('/auth/verify-email',{token}).then(r=>r.data),
    sendOtp: (destination:string,purpose:'phone_verification'|'password_reset'='phone_verification') =>
      api.post<{message:string;otp?:string;expires_in?:number}>('/auth/send-otp',{destination,purpose}).then(r=>r.data),
    verifyOtp: (destination:string,code:string,purpose:'phone_verification'|'password_reset'='phone_verification') =>
      api.post<{message:string}>('/auth/verify-otp',{destination,code,purpose}).then(r=>r.data),
    forgotPassword: (email:string) => api.post<{message:string;otp?:string}>('/auth/forgot-password',{email}).then(r=>r.data),
    resetPassword: (email:string,otp:string,new_password:string) =>
      api.post<{message:string}>('/auth/reset-password',{email,otp,new_password}).then(r=>r.data),
    me: async () => (await api.get<User>('/auth/me')).data,
    updateMe: async (payload:Partial<Pick<User,'full_name'|'phone'|'preferred_language'|'state'|'district'|'profile_picture'|'notification_preferences'>>) =>
      (await api.patch<User>('/auth/me',payload)).data,
    changePassword: (current_password:string,new_password:string) =>
      api.post<{message:string}>('/auth/change-password',{current_password,new_password}).then(r=>r.data),
    sessions: () => api.get<UserSession[]>('/auth/sessions').then(r=>r.data),
    logout: async () => { try { await api.post('/auth/logout') } finally { tokenStore.clear() } },
    logoutAll: async () => { try { await api.post('/auth/logout-all') } finally { tokenStore.clear() } },
    permissions: () => api.get<{role:Role;permissions:string[]}>('/auth/permissions').then(r=>r.data),
    adminUsers: (account_status?:AccountStatus) => api.get<User[]>('/auth/admin/users',{params:account_status?{account_status}:undefined}).then(r=>r.data),
    adminAction: (userId:string,action:'approve'|'reject'|'block'|'unblock'|'delete',reason?:string) =>
      api.post<User>(`/auth/admin/users/${userId}/action`,{action,reason}).then(r=>r.data),
    assignRole: (userId:string,role:Role) => api.put<User>(`/auth/admin/users/${userId}/role`,{role}).then(r=>r.data),
  },
  analytics: () => api.get<DashboardData>('/analytics/dashboard').then(r=>r.data),
  notifications: {
    list: () => api.get<{items:NotificationItem[]}>('/notifications').then(r=>r.data.items.map(item=>({
      ...item,
      body:item.body||`${item.channel.toUpperCase()} notification • ${item.status}`,
      read:item.read??false,
    }))),
    markRead: (id:string) => api.post<{id:string;read:boolean}>(`/notifications/${id}/read`).then(r=>r.data),
  },
  reports: (params?:Record<string,unknown>) => api.get<{items:Report[];total:number}>('/reports',{params}).then(r=>r.data),
  scam: (payload:Record<string,unknown>) => api.post<Prediction & {case_id?:string;scam_probability?:number;detected_keywords?:string[]}>('/ai/scam-detection',payload).then(r=>r.data),
  digitalArrest: {
    analyze: (payload:{caller_number:string;transcript:string;duration:number;video_call:boolean;location?:string;country?:string;spoof_detected?:boolean;telecom_signals?:TelecomSignals}) =>
      api.post<DigitalArrestResult>('/digital-arrest/analyze',payload).then(r=>r.data),
    analyzeAudio: (file:File,payload:{caller_number:string;duration:number;video_call:boolean;location?:string;country?:string;spoof_detected?:boolean}) => {
      const form=new FormData();form.append('audio',file)
      Object.entries(payload).forEach(([key,value])=>{if(value!==undefined)form.append(key,String(value))})
      return api.post<DigitalArrestResult>('/digital-arrest/analyze-audio',form).then(r=>r.data)
    },
    history: (caller_number?:string) => api.get<DigitalArrestHistory[]>('/digital-arrest/history',{params:caller_number?{caller_number}:undefined}).then(r=>r.data),
    dashboard: () => api.get<DigitalArrestDashboard>('/digital-arrest/dashboard').then(r=>r.data),
    action: (caseId:string,action:'block'|'notify_police'|'save_report') =>
      api.post(`/digital-arrest/${caseId}/actions`,{action}).then(r=>r.data),
    report: (caseId:string) => api.post('/digital-arrest/report',{case_id:caseId,total_victims:1}).then(r=>r.data),
    evidence: async (caseId:string) => {
      const response=await api.get<Blob>(`/digital-arrest/${caseId}/evidence.pdf`,{responseType:'blob'})
      const url=URL.createObjectURL(response.data);const link=document.createElement('a')
      link.href=url;link.download=`shieldiq-${caseId}.pdf`;link.click();URL.revokeObjectURL(url)
    },
    startLive: (payload:{caller_number:string;video_call:boolean;consent_confirmed:boolean;telecom_signals?:TelecomSignals}) =>
      api.post<{session_id:string;status:string}>('/digital-arrest/live/start',payload).then(r=>r.data),
    liveChunk: (sessionId:string,payload:{text:string;duration:number;final?:boolean}) =>
      api.post<DigitalArrestResult & {session_id:string;status:string}>(`/digital-arrest/live/${sessionId}/chunk`,payload).then(r=>r.data),
    finalizeLive: (sessionId:string) =>
      api.post<DigitalArrestResult>(`/digital-arrest/live/${sessionId}/finalize`).then(r=>r.data),
    externalAction: (caseId:string,payload:{integration:'mha'|'bank';action:'submit_alert'|'request_payment_hold';transaction_id?:string;account_reference?:string;amount?:number;reason?:string}) =>
      api.post<{dispatch_id:string;integration:string;action:string;status:string;response:Record<string,unknown>}>(`/digital-arrest/${caseId}/external-action`,payload).then(r=>r.data),
  },
  currency: {
    analyze: (file:File,location?:string) => {
      const form = new FormData(); form.append('image',file);if(location)form.append('location',location)
      return api.post<CurrencyResult>('/currency/analyze',form).then(r=>r.data)
    },
    analyzeMultispectral: (file:File,uv?:File|null,infrared?:File|null,location?:string) => {
      const form=new FormData();form.append('image',file)
      if(uv)form.append('uv_image',uv);if(infrared)form.append('infrared_image',infrared)
      if(location)form.append('location',location)
      return api.post<CurrencyResult>('/currency/analyze-multispectral',form).then(r=>r.data)
    },
    modelCard: () => api.get<Record<string,unknown>>('/currency/model-card').then(r=>r.data),
    review: (caseId:string,ground_truth:'genuine'|'counterfeit',verification_method:string,notes?:string) =>
      api.post(`/currency/${caseId}/review`,{ground_truth,verification_method,notes}).then(r=>r.data),
    history: () => api.get<CurrencyHistory[]>('/currency/history').then(r=>r.data),
    statistics: () => api.get<CurrencyStatistics>('/currency/statistics').then(r=>r.data),
    report: async (caseId:string) => {
      const response=await api.get<Blob>(`/currency/${caseId}/report.pdf`,{responseType:'blob'})
      const url=URL.createObjectURL(response.data);const link=document.createElement('a')
      link.href=url;link.download=`currency-${caseId}.pdf`;link.click();URL.revokeObjectURL(url)
    },
  },
  graph: () => api.get('/graph/operational-network').then(r=>r.data),
  graphOperations: {
    feeds: () => api.get('/graph/feeds').then(r=>r.data),
    ingestion: () => api.get('/graph/ingestion/status').then(r=>r.data),
    exchanges: () => api.get('/graph/exchanges').then(r=>r.data),
    acknowledgeExchange: (id:string) => api.post(`/graph/exchanges/${id}/acknowledge`).then(r=>r.data),
    acquireEvidence: (payload:{file:File;case_reference:string;title:string;evidence_type:string;location?:string}) => {
      const form=new FormData();form.append('file',payload.file);form.append('case_reference',payload.case_reference)
      form.append('title',payload.title);form.append('evidence_type',payload.evidence_type)
      if(payload.location)form.append('location',payload.location)
      return api.post('/graph/evidence',form).then(r=>r.data)
    },
    verifyEvidence: (id:string) => api.get(`/graph/evidence/${id}/verify`).then(r=>r.data),
  },
  hotspots: () => api.get('/ai/hotspots').then(r=>r.data),
  heatmap: (params?:Record<string,unknown>) => api.get('/crime/heatmap',{params}).then(r=>r.data),
  geospatial: {
    hotspots: () => api.get('/crime/hotspots',{params:{limit:100}}).then(r=>r.data),
    patrolPlan: (district?:string) => api.get('/crime/patrol-plan',{params:district?{district}:undefined}).then(r=>r.data),
    shares: (district?:string) => api.get('/crime/shares',{params:district?{district}:undefined}).then(r=>r.data),
    share: (payload:{source_district:string;target_district:string;title:string;summary:string;severity:string;incident_ids:string[]}) =>
      api.post('/crime/shares',payload).then(r=>r.data),
    acknowledge: (id:string) => api.post(`/crime/shares/${id}/acknowledge`).then(r=>r.data),
    feeds: () => api.get('/crime/feeds').then(r=>r.data),
  },
  assistantProviders: () => api.get<{default:AssistantProvider;providers:AssistantProviderInfo[]}>('/assistant/providers').then(r=>r.data),
  chat: (text:string,file?:File|null,language='en',provider:AssistantProvider='auto',contextType:'auto'|'currency'|'report'|'none'='auto',contextId='') => {
    const form = new FormData(); form.append('text',text);form.append('language',language);form.append('provider',provider);form.append('context_type',contextType)
    if(contextId.trim())form.append('context_id',contextId.trim())
    if(file){
      const field=file.type.startsWith('image/')?'image':file.type.startsWith('audio/')?'voice':file.type==='application/pdf'?'pdf':''
      if(!field)throw new Error('Attach an image, audio file, or PDF.')
      form.append(field,file)
    }
    return api.post<AssistantReply>('/assistant/chat',form).then(r=>r.data)
  },
  speech: {
    start: (language:string) => api.post<{stream_id:string;status:string}>('/assistant/speech/stream/start',{language}).then(r=>r.data),
    chunk: (streamId:string,file:Blob) => {
      const form=new FormData();form.append('audio',file,'live-chunk.webm')
      return api.post(`/assistant/speech/stream/${streamId}/chunk`,form).then(r=>r.data)
    },
    transcript: (streamId:string,text:string) =>
      api.post(`/assistant/speech/stream/${streamId}/transcript`,{text}).then(r=>r.data),
    finalize: (streamId:string) => api.post(`/assistant/speech/stream/${streamId}/finalize`).then(r=>r.data),
  },
  submitNcrb: (analysisId:string) => api.post(`/assistant/analyses/${analysisId}/ncrb-submit`).then(r=>r.data),
}

export const websocketUrl = (channel:string) => {
  const token = tokenStore.get()?.access_token || ''
  return `${API_URL.replace(/^http/,'ws')}/ws/${channel}?token=${encodeURIComponent(token)}`
}
