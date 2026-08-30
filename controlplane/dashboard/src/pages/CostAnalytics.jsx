import { useEffect, useState } from 'react'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, LineChart, Line, CartesianGrid, ReferenceLine } from 'recharts'
import { getCostMetrics, getOverview } from '../api'
import { fmtCost } from '../utils'

export default function CostAnalytics() {
  const [data, setData]   = useState(null)
  const [baseline, setBaseline] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    Promise.all([getCostMetrics(), getOverview()])
      .then(([cost, overview]) => {
        setData(cost)
        setBaseline(overview.cost_baseline || null)
      })
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <div className="spinner" />
  if (!data)   return <div className="empty-state">No cost data available.</div>

  const totalCost   = (data.model_breakdown || []).reduce((s, m) => s + m.total_cost, 0)
  const totalReqs   = (data.model_breakdown || []).reduce((s, m) => s + m.request_count, 0)

  return (
    <div>
      <div className="metrics-grid" style={{ marginBottom: 20 }}>
        {[
          { label: 'Total Cost (24h)', value: fmtCost(totalCost), color: '#10b981' },
          { label: 'Total Requests',  value: totalReqs.toLocaleString(), color: '#3b82f6' },
          { label: 'Avg Cost/Req',    value: fmtCost(totalCost / Math.max(totalReqs, 1)), color: '#f59e0b' },
          { label: 'Models Used',     value: (data.model_breakdown || []).length, color: '#8b5cf6' },
        ].map(m => (
          <div className="metric-card" key={m.label}>
            <div className="metric-value" style={{ color: m.color, fontSize: 22 }}>{m.value}</div>
            <div className="metric-label">{m.label}</div>
          </div>
        ))}
      </div>

      {/* Cost Baseline Card */}
      {baseline?.sufficient_data && (
        <div className="card" style={{ marginBottom: 16, display: 'flex', gap: 24, alignItems: 'center', padding: '14px 20px' }}>
          <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-secondary)' }}>
            Cost Baseline <span style={{ fontSize: 11, color: 'var(--text-muted)', fontWeight: 400 }}>({baseline.sample_size} samples)</span>
          </div>
          {[
            { label: 'P50', value: baseline.cost.p50, color: '#10b981' },
            { label: 'P90', value: baseline.cost.p90, color: '#f59e0b' },
            { label: 'P95', value: baseline.cost.p95, color: '#ef4444' },
            { label: 'Anomaly Threshold', value: baseline.cost.anomaly_threshold, color: '#dc2626' },
          ].map(b => (
            <div key={b.label} style={{ textAlign: 'center' }}>
              <div style={{ fontSize: 16, fontWeight: 700, color: b.color }}>{fmtCost(b.value)}</div>
              <div style={{ fontSize: 10, color: 'var(--text-muted)' }}>{b.label}</div>
            </div>
          ))}
        </div>
      )}

      <div className="charts-row">
        <div className="card">
          <div className="chart-title">Cost Over Time</div>
          <ResponsiveContainer width="100%" height={220}>
            <LineChart data={data.time_series} margin={{ top: 4, right: 8, left: -20, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
              <XAxis dataKey="hour" tick={{ fill: '#4a5568', fontSize: 10 }} tickLine={false} axisLine={false} />
              <YAxis tickFormatter={v => `$${v.toFixed(3)}`} tick={{ fill: '#4a5568', fontSize: 10 }} tickLine={false} axisLine={false} />
              <Tooltip formatter={v => fmtCost(v)} contentStyle={{ background: '#fff', border: '1px solid #e5e7eb', borderRadius: 8, fontSize: 12, boxShadow: '0 4px 12px rgba(0,0,0,0.08)' }} />
              <Line type="monotone" dataKey="cost_usd" stroke="#10b981" strokeWidth={2} dot={false} name="Cost (USD)" />
              {baseline?.sufficient_data && (
                <ReferenceLine y={baseline.cost.p90} stroke="#f59e0b" strokeDasharray="6 3" label={{ value: `P90: ${fmtCost(baseline.cost.p90)}`, fill: '#f59e0b', fontSize: 10, position: 'right' }} />
              )}
            </LineChart>
          </ResponsiveContainer>
        </div>

        <div className="card">
          <div className="chart-title">Cost by Model</div>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={data.model_breakdown} layout="vertical" margin={{ top: 4, right: 16, left: 10, bottom: 0 }}>
              <XAxis type="number" tickFormatter={v => `$${v.toFixed(3)}`} tick={{ fill: '#4a5568', fontSize: 10 }} tickLine={false} axisLine={false} />
              <YAxis type="category" dataKey="model" tick={{ fill: '#6b7280', fontSize: 11 }} tickLine={false} axisLine={false} width={110} />
              <Tooltip formatter={v => fmtCost(v)} contentStyle={{ background: '#fff', border: '1px solid #e5e7eb', borderRadius: 8, fontSize: 12, boxShadow: '0 4px 12px rgba(0,0,0,0.08)' }} />
              <Bar dataKey="total_cost" fill="#3b82f6" radius={[0, 4, 4, 0]} name="Total Cost" />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Model breakdown table */}
      <div className="card" style={{ marginTop: 16 }}>
        <div className="card-title" style={{ marginBottom: 12 }}>Model Breakdown</div>
        <table className="data-table">
          <thead>
            <tr><th>Model</th><th>Requests</th><th>Total Cost</th><th>Avg Cost / Req</th></tr>
          </thead>
          <tbody>
            {(data.model_breakdown || []).map(m => (
              <tr key={m.model}>
                <td className="mono">{m.model}</td>
                <td>{m.request_count.toLocaleString()}</td>
                <td style={{ color: '#10b981', fontWeight: 600 }}>{fmtCost(m.total_cost)}</td>
                <td>{fmtCost(m.avg_cost)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
