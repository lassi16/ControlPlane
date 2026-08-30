import axios from 'axios'

// ── Base URL ──────────────────────────────────────────────────────────────────
const isLocal = typeof window !== 'undefined' &&
  (window.location.hostname === 'localhost' ||
   window.location.hostname === '127.0.0.1')

const RENDER_URL = 'https://controlplane-api.onrender.com'

const BASE_URL = import.meta.env.VITE_API_BASE ||
  (isLocal ? 'http://localhost:8000' : RENDER_URL)

const api = axios.create({
  baseURL: BASE_URL,
  timeout: 30000,
})

// ── In-memory cache (30s TTL) ─────────────────────────────────────────────────
const _cache = new Map()
const TTL = 30_000   // 30 seconds

function cached(key, fetcher) {
  const hit = _cache.get(key)
  if (hit && Date.now() - hit.ts < TTL) return Promise.resolve(hit.data)
  return fetcher().then(data => {
    _cache.set(key, { data, ts: Date.now() })
    return data
  })
}

/** Force-invalidate a cache key (call after sending a chat message) */
export function invalidateCache(key) {
  if (key) _cache.delete(key)
  else _cache.clear()
}

// ── Keep Render free tier awake (ping every 10 min) ───────────────────────────
let _pingTimer = null
export function startKeepAlive() {
  if (_pingTimer) return
  // Ping immediately on app load — wakes Render if sleeping
  api.get('/health').catch(() => {})
  _pingTimer = setInterval(() => {
    api.get('/health').catch(() => {})
  }, 10 * 60 * 1000)  // every 10 minutes
}

// ── API calls (all cached) ────────────────────────────────────────────────────
export const getOverview = () =>
  cached('overview', () => api.get('/api/dashboard/overview').then(r => r.data))

export const getEvents = (params) => {
  const key = 'events:' + JSON.stringify(params || {})
  return cached(key, () => api.get('/api/dashboard/events', { params }).then(r => r.data))
}

export const getEventDetail = (id) =>
  cached(`event:${id}`, () => api.get(`/api/dashboard/events/${id}`).then(r => r.data))

export const getHallucinationMetrics = () =>
  cached('hallucination', () => api.get('/api/dashboard/metrics/hallucination').then(r => r.data))

export const getCostMetrics = () =>
  cached('cost', () => api.get('/api/dashboard/metrics/cost').then(r => r.data))

export const getPIIMetrics = () =>
  cached('pii', () => api.get('/api/dashboard/metrics/pii').then(r => r.data))

export const getAlerts = () =>
  cached('alerts', () => api.get('/api/dashboard/alerts').then(r => r.data))

// Chat is NOT cached — always live
export const sendChat = (messages, appId = 'demo', demoMode = false) =>
  api.post('/v1/chat/completions', {
    model: 'openai/gpt-oss-20b',
    messages,
    controlplane: { application_id: appId, demo_mode: demoMode },
  }).then(r => r.data)

// Review submission — NOT cached
export const submitReview = (eventId, decision, notes = '') =>
  api.post(`/api/dashboard/review/${eventId}`, { decision, notes }).then(r => r.data)

export default api
