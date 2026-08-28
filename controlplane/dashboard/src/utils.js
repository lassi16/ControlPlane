export const ACTION_COLORS = {
  allow: '#10b981', annotate: '#3b82f6', warn: '#f59e0b',
  redact: '#f97316', block: '#ef4444', escalate: '#8b5cf6',
}
export const IMPACT_COLORS = {
  low: '#10b981', medium: '#f59e0b', high: '#f97316', critical: '#ef4444',
}
export const CLAIM_STATUS_COLORS = {
  SUPPORTED: '#10b981', CONTRADICTED: '#ef4444', UNKNOWN: '#f59e0b',
  NOT_VERIFIABLE: '#6b7280', pending: '#8b5cf6',
}

export function fmtCost(v) {
  if (v == null) return '—'
  if (v < 0.001) return `$${(v * 1000).toFixed(3)}m`
  return `$${v.toFixed(4)}`
}

export function fmtPct(v) {
  if (v == null) return '—'
  return `${(v * 100).toFixed(1)}%`
}

export function fmtTs(ts) {
  if (!ts) return '—'
  const d = new Date(ts * 1000)
  return d.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' })
}

export function truncate(str, n = 60) {
  if (!str) return ''
  return str.length > n ? str.slice(0, n) + '…' : str
}

export function riskColor(score) {
  if (score > 0.7) return '#ef4444'
  if (score > 0.4) return '#f97316'
  if (score > 0.2) return '#f59e0b'
  return '#10b981'
}
