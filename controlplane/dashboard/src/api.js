import axios from 'axios'

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE || '',
  timeout: 15000,
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
