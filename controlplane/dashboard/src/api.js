import axios from 'axios'

// Production fallback: if VITE_API_BASE not set and we're not on localhost,
// use the Render backend URL automatically
const isLocal = typeof window !== 'undefined' &&
  (window.location.hostname === 'localhost' ||
   window.location.hostname === '127.0.0.1')

const RENDER_URL = 'https://controlplane-api.onrender.com'

const BASE_URL = import.meta.env.VITE_API_BASE ||
  (isLocal ? 'http://localhost:8000' : RENDER_URL)

const api = axios.create({
  baseURL: BASE_URL,
  timeout: 30000, // 30s — Render free tier can be slow on wake-up
})

export const getOverview    = () => api.get('/api/dashboard/overview').then(r => r.data)
export const getEvents      = (params) => api.get('/api/dashboard/events', { params }).then(r => r.data)
export const getEventDetail = (id) => api.get(`/api/dashboard/events/${id}`).then(r => r.data)
export const getHallucinationMetrics = () => api.get('/api/dashboard/metrics/hallucination').then(r => r.data)
export const getCostMetrics = () => api.get('/api/dashboard/metrics/cost').then(r => r.data)
export const getPIIMetrics  = () => api.get('/api/dashboard/metrics/pii').then(r => r.data)
export const getAlerts      = () => api.get('/api/dashboard/alerts').then(r => r.data)

export const sendChat = (messages, appId = 'demo', demoMode = false) =>
  api.post('/v1/chat/completions', {
    model: 'openai/gpt-oss-20b',
    messages,
    controlplane: { application_id: appId, demo_mode: demoMode },
  }).then(r => r.data)

export default api
