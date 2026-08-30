import { useEffect, useState } from 'react'
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, PieChart, Pie, Cell, Legend } from 'recharts'
import { AlertTriangle, Shield, DollarSign, Activity, Zap, Eye, Clock } from 'lucide-react'
import { getOverview, getEvents } from '../api'
import { ACTION_COLORS, IMPACT_COLORS, fmtCost, fmtPct, fmtTs, truncate } from '../utils'

const DONUT_COLORS = ['#10b981', '#3b82f6', '#f59e0b', '#f97316', '#ef4444', '#8b5cf6']

export default function Overview({ onEventClick }) {
  const [data, setData]     = useState(null)
  const [events, setEvents] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    Promise.all([getOverview(), getEvents({ limit: 8 })])
      .then(([ov, ev]) => { setData(ov); setEvents(ev.events || []) })
      .catch(console.error)
      .finally(() => setLoading(false))

    const t = setInterval(() => {
      getOverview().then(setData).catch(() => {})
    }, 8000)
    return () => clearInterval(t)
  }, [])

  if (loading) return (
    <div>
      <div className="metrics-grid">
        {[...Array(6)].map((_, i) => <div key={i} className="skeleton-metric" />)}
      </div>
      <div className="charts-row">
        <div className="skeleton-card"><div className="skeleton skeleton-title" /><div className="skeleton" style={{ height: 180 }} /></div>
        <div className="skeleton-card"><div className="skeleton skeleton-title" /><div className="skeleton" style={{ height: 180 }} /></div>
      </div>
      <div className="skeleton-card">
        <div className="skeleton skeleton-title" />
        {[...Array(6)].map((_, i) => <div key={i} className="skeleton-row" />)}
      </div>
    </div>
  )
  if (!data)   return <div className="empty-state">Failed to load data. Is the gateway running?</div>

  const actionDist = [
    { name: 'Allow',    value: data.allowed,   color: ACTION_COLORS.allow },
    { name: 'Annotate', value: data.annotated, color: ACTION_COLORS.annotate },
    { name: 'Warn',     value: data.escalated, color: ACTION_COLORS.warn },
    { name: 'Redact',   value: data.redacted,  color: ACTION_COLORS.redact },
    { name: 'Block',    value: data.blocked,   color: ACTION_COLORS.block },
  ].filter(d => d.value > 0)

  const metrics = [
    {
      label: 'Total Requests', value: data.total_requests.toLocaleString(),
      icon: Activity, color: '#3b82f6', gradient: 'linear-gradient(90deg,#3b82f6,#06b6d4)',
      delta: null,
    },
    {
      label: 'Blocked', value: data.blocked.toLocaleString(),
      icon: Shield, color: '#ef4444', gradient: 'linear-gradient(90deg,#ef4444,#dc2626)',
      delta: data.total_requests ? `${((data.blocked / data.total_requests) * 100).toFixed(1)}%` : '—',
    },
    {
      label: 'PII Incidents', value: data.pii_incidents.toLocaleString(),
      icon: Eye, color: '#f97316', gradient: 'linear-gradient(90deg,#f97316,#ea580c)',
      delta: null,
    },
    {
      label: 'Hallucination Rate', value: fmtPct(data.hallucination_rate),
      icon: Zap, color: '#f59e0b', gradient: 'linear-gradient(90deg,#f59e0b,#d97706)',
      delta: null,
    },
    {
      label: 'Total Cost', value: fmtCost(data.total_cost_usd),
      icon: DollarSign, color: '#10b981', gradient: 'linear-gradient(90deg,#10b981,#059669)',
      delta: data.cost_baseline?.sufficient_data
        ? `P90: ${fmtCost(data.cost_baseline.cost.p90)}/req`
        : `avg ${fmtCost(data.avg_cost_per_request)}/req`,
    },
    {
      label: 'Needs Review', value: (data.blocked + data.escalated).toLocaleString(),
      icon: AlertTriangle, color: '#8b5cf6', gradient: 'linear-gradient(90deg,#8b5cf6,#7c3aed)',
      delta: `${data.deep_checks_pending || 0} deep checks pending`,
    },
  ]

  return (
    <div>
      {/* Alerts */}
      {data.alerts?.map((alert, i) => (
        <div key={i} className={`alert-bar ${alert.severity}`}>
          <AlertTriangle size={15} />
          <strong>{alert.type}:</strong> {alert.message}
        </div>
      ))}

      {/* Metric Cards */}
      <div className="metrics-grid">
        {metrics.map(m => (
          <div className="metric-card" key={m.label} style={{ '--accent-gradient': m.gradient }}>
            <div className="metric-icon" style={{ background: m.color + '22' }}>
              <m.icon size={18} color={m.color} />
            </div>
            <div className="metric-value" style={{ color: m.color }}>{m.value}</div>
            <div className="metric-label">{m.label}</div>
            {m.delta && <div className="metric-delta neutral">{m.delta}</div>}
          </div>
        ))}
      </div>

      {/* Charts Row */}
      <div className="charts-row">
        {/* Request volume + blocked */}
        <div className="card">
          <div className="chart-title">Request Volume — Last 24 Hours</div>
          <ResponsiveContainer width="100%" height={200}>
            <AreaChart data={data.time_series} margin={{ top: 4, right: 4, left: -20, bottom: 0 }}>
              <defs>
                <linearGradient id="gReq" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%"  stopColor="#3b82f6" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
                </linearGradient>
                <linearGradient id="gBlk" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%"  stopColor="#ef4444" stopOpacity={0.4} />
                  <stop offset="95%" stopColor="#ef4444" stopOpacity={0} />
                </linearGradient>
              </defs>
              <XAxis dataKey="hour" tick={{ fill: '#4a5568', fontSize: 10 }} tickLine={false} axisLine={false} />
              <YAxis tick={{ fill: '#4a5568', fontSize: 10 }} tickLine={false} axisLine={false} />
<Tooltip contentStyle={{ background: '#fff', border: '1px solid #e5e7eb', borderRadius: 8, fontSize: 12, boxShadow: '0 4px 12px rgba(0,0,0,0.08)' }} />
              <Area type="monotone" dataKey="requests" stroke="#3b82f6" fill="url(#gReq)" strokeWidth={2} name="Requests" />
              <Area type="monotone" dataKey="blocked"  stroke="#ef4444" fill="url(#gBlk)" strokeWidth={2} name="Blocked" />
            </AreaChart>
          </ResponsiveContainer>
        </div>

        {/* Action Distribution */}
        <div className="card">
          <div className="chart-title">Policy Actions</div>
          <ResponsiveContainer width="100%" height={200}>
            <PieChart>
              <Pie data={actionDist} cx="50%" cy="50%" innerRadius={55} outerRadius={85} dataKey="value" paddingAngle={2}>
                {actionDist.map((entry, i) => <Cell key={i} fill={entry.color} />)}
              </Pie>
              <Tooltip contentStyle={{ background: '#fff', border: '1px solid #e5e7eb', borderRadius: 8, fontSize: 12, boxShadow: '0 4px 12px rgba(0,0,0,0.08)' }} />
              <Legend formatter={(v) => <span style={{ color: '#6b7280', fontSize: 11 }}>{v}</span>} />
            </PieChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Recent Events */}
      <div className="card">
        <div className="card-header">
          <div className="card-title">Recent Requests</div>
          <Clock size={14} color="var(--text-muted)" />
        </div>
        <table className="data-table">
          <thead>
            <tr>
              <th>Time</th>
              <th>Application</th>
              <th>Query</th>
              <th>Model</th>
              <th>Impact</th>
              <th>Action</th>
              <th>Cost</th>
            </tr>
          </thead>
          <tbody>
            {events.map(ev => (
              <tr key={ev.id} onClick={() => onEventClick(ev)}>
                <td className="mono text-muted">{fmtTs(ev.timestamp)}</td>
                <td><span style={{ fontSize: 11, background: 'var(--bg-elevated)', padding: '2px 7px', borderRadius: 4 }}>{ev.application_id}</span></td>
                <td style={{ maxWidth: 220 }}>{truncate(ev.user_query, 55)}</td>
                <td className="mono text-secondary" style={{ fontSize: 11 }}>{ev.model_id}</td>
                <td><span className={`badge badge-${ev.impact_rescored}`}>{ev.impact_rescored}</span></td>
                <td><span className={`badge badge-${ev.policy_action}`}>{ev.policy_action}</span></td>
                <td className="mono">{fmtCost(ev.actual_cost)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
