import { useEffect, useState } from 'react'
import { getEvents, submitReview } from '../api'
import { fmtTs, truncate, fmtPct } from '../utils'
import { Users, Check, X, HelpCircle } from 'lucide-react'

export default function ReviewQueue({ onEventClick }) {
  const [items, setItems]     = useState([])
  const [loading, setLoading] = useState(true)
  const [resolved, setResolved] = useState({})

  useEffect(() => {
    // Pull high-risk events as proxy for review queue (no separate DB in demo)
    getEvents({ limit: 200 }).then(d => {
      const queue = (d.events || [])
        .filter(e => e.policy_action === 'block' || e.policy_action === 'escalate' ||
                     (e.risk_score || 0) > 0.5)
        .map(e => ({
          ...e,
          priority: e.policy_action === 'escalate' ? 'critical'
                  : (e.risk_score || 0) > 0.7 ? 'high'
                  : 'medium',
        }))
        .sort((a, b) => {
          const order = { critical: 0, high: 1, medium: 2 }
          return order[a.priority] - order[b.priority]
        })
      setItems(queue)
    }).catch(console.error).finally(() => setLoading(false))
  }, [])

  const resolve = (id, label) => {
    setResolved(prev => ({ ...prev, [id]: label }))
    // Fire and forget — send to backend
    submitReview(id, label).catch(() => {})
  }

  const stats = {
    critical: items.filter(i => i.priority === 'critical').length,
    high:     items.filter(i => i.priority === 'high').length,
    medium:   items.filter(i => i.priority === 'medium').length,
    resolved: Object.keys(resolved).length,
  }

  if (loading) return <div className="spinner" />

  return (
    <div>
      <div className="metrics-grid" style={{ marginBottom: 20 }}>
        {[
          { label: 'Critical', value: stats.critical, color: '#ef4444' },
          { label: 'High',     value: stats.high,     color: '#f97316' },
          { label: 'Medium',   value: stats.medium,   color: '#f59e0b' },
          { label: 'Resolved this session', value: stats.resolved, color: '#10b981' },
        ].map(m => (
          <div className="metric-card" key={m.label}>
            <div className="metric-value" style={{ color: m.color, fontSize: 22 }}>{m.value}</div>
            <div className="metric-label">{m.label}</div>
          </div>
        ))}
      </div>

      {items.length === 0 ? (
        <div className="empty-state"><Users size={40} /><p>No items in review queue.</p></div>
      ) : (
        <div>
          {items.map(item => {
            const res = resolved[item.id]
            return (
              <div key={item.id} className="card" style={{
                marginBottom: 12,
                borderColor: item.priority === 'critical' ? 'rgba(239,68,68,0.4)'
                           : item.priority === 'high'     ? 'rgba(249,115,22,0.4)'
                           : 'var(--border)',
                opacity: res ? 0.6 : 1,
              }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 12 }}>
                  <div style={{ flex: 1 }}>
                    <div style={{ display: 'flex', gap: 8, marginBottom: 8, flexWrap: 'wrap' }}>
                      <span className={`badge badge-${item.priority}`}>{item.priority.toUpperCase()} PRIORITY</span>
                      <span className={`badge badge-${item.policy_action}`}>{item.policy_action}</span>
                      <span className={`badge badge-${item.impact_rescored}`}>{item.impact_rescored} impact</span>
                      {item.deep_check_status === 'complete' && item.risk_score != null && (
                        <span style={{ fontSize: 11, color: 'var(--text-muted)', alignSelf: 'center' }}>
                          risk: <strong style={{ color: '#f97316' }}>{fmtPct(item.risk_score)}</strong>
                        </span>
                      )}
                    </div>
                    <div style={{ fontSize: 13, marginBottom: 4 }}>
                      <span style={{ color: 'var(--text-muted)' }}>App:</span> {item.application_id}
                      <span style={{ marginLeft: 12, color: 'var(--text-muted)' }}>Time:</span> {fmtTs(item.timestamp)}
                    </div>
                    <div style={{ fontSize: 13, color: 'var(--text-secondary)', marginBottom: 6 }}>
                      <strong>Q:</strong> {truncate(item.user_query, 100)}
                    </div>
                    {(item.claims || []).filter(c => c.status === 'CONTRADICTED').map((c, i) => (
                      <div key={i} style={{ fontSize: 12, color: '#dc2626', marginTop: 4 }}>
                        ⚠ Contradicted: {truncate(c.text, 90)}
                      </div>
                    ))}
                  </div>

                  <div style={{ display: 'flex', flexDirection: 'column', gap: 6, flexShrink: 0 }}>
                    {res ? (
                      <div style={{ fontSize: 12, color: 'var(--text-muted)', textAlign: 'center', padding: '6px 12px', background: 'var(--bg-elevated)', borderRadius: 6 }}>
                        Marked: <strong style={{ color: res === 'correct' ? '#10b981' : '#ef4444' }}>{res}</strong>
                      </div>
                    ) : (
                      <>
                        <button className="btn btn-success" onClick={() => resolve(item.id, 'correct')} style={{ fontSize: 12 }}>
                          <Check size={12} /> Correct
                        </button>
                        <button className="btn btn-danger" onClick={() => resolve(item.id, 'incorrect')} style={{ fontSize: 12 }}>
                          <X size={12} /> Incorrect
                        </button>
                        <button className="btn btn-ghost" onClick={() => resolve(item.id, 'uncertain')} style={{ fontSize: 12 }}>
                          <HelpCircle size={12} /> Uncertain
                        </button>
                        <button className="btn btn-ghost" onClick={() => onEventClick(item)} style={{ fontSize: 12, marginTop: 4 }}>
                          View Detail
                        </button>
                      </>
                    )}
                  </div>
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
