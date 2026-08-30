import { useEffect, useState } from 'react'
import { getEvents } from '../api'
import { fmtCost, fmtPct, fmtTs, truncate } from '../utils'
import { Search, AlertTriangle } from 'lucide-react'

const ACTIONS = ['', 'allow', 'annotate', 'warn', 'redact', 'block', 'escalate']
const IMPACTS  = ['', 'low', 'medium', 'high', 'critical']

function needsReview(ev) {
  return ev.policy_action === 'block' ||
         ev.policy_action === 'escalate' ||
         (ev.risk_score || 0) > 0.5 ||
         ev.policy_action === 'redact'
}

export default function EventLog({ onEventClick, filter }) {
  const [events, setEvents]   = useState([])
  const [loading, setLoading] = useState(true)
  const [action, setAction]   = useState('')
  const [impact, setImpact]   = useState('')
  const [search, setSearch]   = useState('')
  const [reviewOnly, setReviewOnly] = useState(false)
  const [page, setPage]       = useState(0)
  const PAGE = 30

  useEffect(() => {
    setLoading(true)
    const params = { limit: 200, offset: 0 }
    if (action) params.policy_action = action
    getEvents(params)
      .then(d => setEvents(d.events || []))
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [action])

  // Client-side filter for search + impact + pii filter + review filter
  const filtered = events.filter(ev => {
    if (filter === 'pii' && !ev.tier1_pii?.pii_detected) return false
    if (impact && ev.impact_rescored !== impact) return false
    if (reviewOnly && !needsReview(ev)) return false
    if (search) {
      const q = search.toLowerCase()
      return (ev.user_query || '').toLowerCase().includes(q) ||
             (ev.application_id || '').toLowerCase().includes(q) ||
             (ev.model_id || '').toLowerCase().includes(q)
    }
    return true
  })

  const reviewCount = events.filter(needsReview).length
  const paginated = filtered.slice(page * PAGE, (page + 1) * PAGE)
  const totalPages = Math.ceil(filtered.length / PAGE)

  return (
    <div>
      {/* Filters */}
      <div style={{ display: 'flex', gap: 10, marginBottom: 16, flexWrap: 'wrap', alignItems: 'center' }}>
        <div style={{ position: 'relative', flex: 1, minWidth: 200 }}>
          <Search size={14} style={{ position: 'absolute', left: 10, top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)' }} />
          <input
            placeholder="Search queries, apps, models…"
            value={search}
            onChange={e => { setSearch(e.target.value); setPage(0) }}
            style={{
              width: '100%', padding: '8px 12px 8px 32px',
              background: 'var(--bg-card)', border: '1px solid var(--border)',
              borderRadius: 'var(--radius-sm)', color: 'var(--text-primary)', fontSize: 13,
            }}
          />
        </div>
        <select value={action} onChange={e => { setAction(e.target.value); setPage(0) }}
          style={{ padding: '8px 12px', background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: 'var(--radius-sm)', color: 'var(--text-primary)', fontSize: 13 }}>
          {ACTIONS.map(a => <option key={a} value={a}>{a || 'All Actions'}</option>)}
        </select>
        <select value={impact} onChange={e => { setImpact(e.target.value); setPage(0) }}
          style={{ padding: '8px 12px', background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: 'var(--radius-sm)', color: 'var(--text-primary)', fontSize: 13 }}>
          {IMPACTS.map(i => <option key={i} value={i}>{i || 'All Impacts'}</option>)}
        </select>
        <button
          className={`btn ${reviewOnly ? 'btn-danger' : 'btn-ghost'}`}
          onClick={() => { setReviewOnly(!reviewOnly); setPage(0) }}
          style={{ fontSize: 12, padding: '7px 12px', gap: 5 }}
        >
          <AlertTriangle size={13} />
          Needs Review ({reviewCount})
        </button>
        <div style={{ fontSize: 12, color: 'var(--text-muted)', alignSelf: 'center' }}>
          {filtered.length} events
        </div>
      </div>

      <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
        {loading ? <div className="spinner" /> : (
          <table className="data-table">
            <thead>
              <tr>
                <th>Time</th>
                <th>App</th>
                <th>Query</th>
                <th>Model</th>
                <th>Impact</th>
                <th>Action</th>
                <th>Risk</th>
                <th>Cost</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {paginated.length === 0 ? (
                <tr><td colSpan={9} style={{ textAlign: 'center', padding: 40, color: 'var(--text-muted)' }}>No events match filters</td></tr>
              ) : paginated.map(ev => (
                <tr key={ev.id} onClick={() => onEventClick(ev)} style={{
                  borderLeft: needsReview(ev) ? '3px solid #ef4444' : '3px solid transparent',
                }}>
                  <td className="mono text-muted" style={{ fontSize: 11 }}>{fmtTs(ev.timestamp)}</td>
                  <td><span style={{ fontSize: 11, background: 'var(--bg-elevated)', padding: '2px 7px', borderRadius: 4 }}>{ev.application_id}</span></td>
                  <td style={{ maxWidth: 240 }}>{truncate(ev.user_query, 60)}</td>
                  <td className="mono text-secondary" style={{ fontSize: 11 }}>{ev.model_id}</td>
                  <td><span className={`badge badge-${ev.impact_rescored}`}>{ev.impact_rescored}</span></td>
                  <td><span className={`badge badge-${ev.policy_action}`}>{ev.policy_action}</span></td>
                  <td>
                    {ev.risk_score != null ? (
                      <div className="risk-bar-wrap" style={{ minWidth: 80 }}>
                        <div className="risk-bar-track">
                          <div className="risk-bar-fill" style={{
                            width: `${ev.risk_score * 100}%`,
                            background: ev.risk_score > 0.6 ? '#ef4444' : ev.risk_score > 0.3 ? '#f97316' : '#10b981'
                          }} />
                        </div>
                        <span style={{ fontSize: 10, color: 'var(--text-muted)', width: 28, textAlign: 'right' }}>
                          {fmtPct(ev.risk_score)}
                        </span>
                      </div>
                    ) : <span className="text-muted">—</span>}
                  </td>
                  <td className="mono" style={{ fontSize: 11 }}>{fmtCost(ev.actual_cost)}</td>
                  <td>
                    {needsReview(ev) ? (
                      <span style={{
                        fontSize: 10, padding: '3px 8px', borderRadius: 99, fontWeight: 600,
                        background: '#fef2f2', color: '#dc2626', border: '1px solid #fecaca',
                      }}>REVIEW</span>
                    ) : (
                      <span style={{
                        fontSize: 10, padding: '3px 8px', borderRadius: 99,
                        background: ev.deep_check_status === 'complete' ? 'rgba(16,185,129,0.1)' : 'rgba(75,85,99,0.15)',
                        color: ev.deep_check_status === 'complete' ? '#10b981' : 'var(--text-muted)',
                      }}>{ev.deep_check_status === 'complete' ? 'VERIFIED' : ev.deep_check_status}</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}

        {/* Pagination */}
        {totalPages > 1 && (
          <div style={{ display: 'flex', gap: 8, justifyContent: 'center', padding: '12px', borderTop: '1px solid var(--border)' }}>
            <button className="btn btn-ghost" onClick={() => setPage(p => Math.max(0, p - 1))} disabled={page === 0}>Prev</button>
            <span style={{ alignSelf: 'center', fontSize: 12, color: 'var(--text-muted)' }}>Page {page + 1} / {totalPages}</span>
            <button className="btn btn-ghost" onClick={() => setPage(p => Math.min(totalPages - 1, p + 1))} disabled={page === totalPages - 1}>Next</button>
          </div>
        )}
      </div>
    </div>
  )
}
