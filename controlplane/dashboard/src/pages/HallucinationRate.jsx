import { useEffect, useState } from 'react'
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, Legend, ReferenceLine } from 'recharts'
import { getHallucinationMetrics, getEvents } from '../api'
import { fmtPct } from '../utils'
import { Zap } from 'lucide-react'

export default function HallucinationRate() {
  const [series, setSeries]   = useState([])
  const [events, setEvents]   = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    Promise.all([getHallucinationMetrics(), getEvents({ limit: 100 })])
      .then(([h, ev]) => { setSeries(h.series || []); setEvents(ev.events || []) })
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <div className="spinner" />

  const avgContradiction = series.length
    ? series.reduce((s, p) => s + p.contradiction_rate, 0) / series.length : 0
  const avgRisk = series.length
    ? series.reduce((s, p) => s + p.risk_score, 0) / series.length : 0

  const contradicted = events.filter(e =>
    (e.claims || []).some(c => c.status === 'CONTRADICTED')
  )

  return (
    <div>
      {/* Summary Cards */}
      <div className="metrics-grid" style={{ marginBottom: 20 }}>
        {[
          { label: 'Avg Contradiction Rate', value: fmtPct(avgContradiction), color: '#ef4444' },
          { label: 'Avg Risk Score',          value: fmtPct(avgRisk),          color: '#f97316' },
          { label: 'Events with Contradictions', value: contradicted.length, color: '#f59e0b' },
          { label: 'Deep Checks Completed',
            value: events.filter(e => e.deep_check_status === 'complete').length,
            color: '#10b981' },
        ].map(m => (
          <div className="metric-card" key={m.label}>
            <div className="metric-value" style={{ color: m.color, fontSize: 22 }}>{m.value}</div>
            <div className="metric-label">{m.label}</div>
          </div>
        ))}
      </div>

      {/* Time Series */}
      <div className="card" style={{ marginBottom: 16 }}>
        <div className="chart-title">
          Contradiction Rate & Risk Score — 24h
          <div className="chart-subtitle">Policy target: &lt;10% contradiction rate</div>
        </div>
        <ResponsiveContainer width="100%" height={260}>
          <LineChart data={series} margin={{ top: 4, right: 8, left: -20, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(30,45,69,0.6)" />
            <XAxis dataKey="hour" tick={{ fill: '#4a5568', fontSize: 10 }} tickLine={false} axisLine={false} label={{ value: 'Hour', position: 'insideBottom', offset: -2, fill: '#4a5568', fontSize: 10 }} />
            <YAxis tickFormatter={v => `${(v * 100).toFixed(0)}%`} tick={{ fill: '#4a5568', fontSize: 10 }} tickLine={false} axisLine={false} />
            <Tooltip formatter={v => fmtPct(v)} contentStyle={{ background: '#1a2234', border: '1px solid #1e2d45', borderRadius: 8, fontSize: 12 }} />
            <Legend formatter={v => <span style={{ color: '#8b9ab5', fontSize: 11 }}>{v}</span>} />
            <ReferenceLine y={0.1} stroke="#ef444455" strokeDasharray="4 4" label={{ value: 'Target', fill: '#ef4444', fontSize: 10 }} />
            <Line type="monotone" dataKey="contradiction_rate" stroke="#ef4444" strokeWidth={2} dot={false} name="Contradiction Rate" />
            <Line type="monotone" dataKey="risk_score"         stroke="#f97316" strokeWidth={2} dot={false} name="Risk Score" strokeDasharray="4 2" />
          </LineChart>
        </ResponsiveContainer>
      </div>

      {/* Contradicted claims table */}
      <div className="card">
        <div className="card-title" style={{ marginBottom: 12 }}>Events with Contradicted Claims</div>
        {contradicted.length === 0 ? (
          <div className="empty-state"><Zap size={32} /><p>No contradictions found in loaded events.</p></div>
        ) : (
          <table className="data-table">
            <thead>
              <tr><th>Query</th><th>Contradicted Claim</th><th>Risk</th><th>Action</th></tr>
            </thead>
            <tbody>
              {contradicted.slice(0, 20).map(ev => {
                const bad = (ev.claims || []).find(c => c.status === 'CONTRADICTED')
                return (
                  <tr key={ev.id}>
                    <td style={{ maxWidth: 200, fontSize: 12 }}>{ev.user_query?.slice(0, 60)}…</td>
                    <td style={{ maxWidth: 260, fontSize: 12, color: '#fca5a5' }}>{bad?.text?.slice(0, 80)}…</td>
                    <td><span style={{ color: '#ef4444', fontWeight: 700 }}>{fmtPct(ev.risk_score)}</span></td>
                    <td><span className={`badge badge-${ev.policy_action}`}>{ev.policy_action}</span></td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}
