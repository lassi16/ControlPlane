import { useEffect, useState } from 'react'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, LineChart, Line, CartesianGrid } from 'recharts'
import { getCostMetrics } from '../api'
import { fmtCost } from '../utils'

export default function CostAnalytics() {
  const [data, setData]   = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    getCostMetrics().then(setData).catch(console.error).finally(() => setLoading(false))
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

      <div className="charts-row">
        <div className="card">
          <div className="chart-title">Cost Over Time</div>
          <ResponsiveContainer width="100%" height={220}>
            <LineChart data={data.time_series} margin={{ top: 4, right: 8, left: -20, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(30,45,69,0.6)" />
              <XAxis dataKey="hour" tick={{ fill: '#4a5568', fontSize: 10 }} tickLine={false} axisLine={false} />
              <YAxis tickFormatter={v => `$${v.toFixed(3)}`} tick={{ fill: '#4a5568', fontSize: 10 }} tickLine={false} axisLine={false} />
              <Tooltip formatter={v => fmtCost(v)} contentStyle={{ background: '#1a2234', border: '1px solid #1e2d45', borderRadius: 8, fontSize: 12 }} />
              <Line type="monotone" dataKey="cost_usd" stroke="#10b981" strokeWidth={2} dot={false} name="Cost (USD)" />
            </LineChart>
          </ResponsiveContainer>
        </div>

        <div className="card">
          <div className="chart-title">Cost by Model</div>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={data.model_breakdown} layout="vertical" margin={{ top: 4, right: 16, left: 10, bottom: 0 }}>
              <XAxis type="number" tickFormatter={v => `$${v.toFixed(3)}`} tick={{ fill: '#4a5568', fontSize: 10 }} tickLine={false} axisLine={false} />
              <YAxis type="category" dataKey="model" tick={{ fill: '#8b9ab5', fontSize: 11 }} tickLine={false} axisLine={false} width={110} />
              <Tooltip formatter={v => fmtCost(v)} contentStyle={{ background: '#1a2234', border: '1px solid #1e2d45', borderRadius: 8, fontSize: 12 }} />
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
