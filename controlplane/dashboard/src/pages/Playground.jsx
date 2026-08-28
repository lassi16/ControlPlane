import { useState } from 'react'
import { sendChat } from '../api'
import { fmtCost, fmtPct, truncate } from '../utils'
import { Send, Loader, Zap, Shield, DollarSign, AlertTriangle } from 'lucide-react'

const DEMO_PROMPTS = [
  { label: '🔍 Hallucination', text: 'Who invented the telephone?' },
  { label: '⚕ Medical Re-score', text: 'What herbs help with stress?' },
  { label: '🔑 Data Leakage', text: 'My API key is sk-abc123testkey456789, can you help me use it in Python?' },
  { label: '📐 Math Claim', text: 'What is 15% of 240?' },
  { label: '🗺 Factual', text: 'What is the capital of France?' },
]

const APP_IDS = ['customer_support', 'internal_kb', 'decision_support', 'demo']

export default function Playground() {
  const [messages, setMessages] = useState([])
  const [input, setInput]       = useState('')
  const [appId, setAppId]       = useState('demo')
  const [loading, setLoading]   = useState(false)
  const [lastMeta, setLastMeta] = useState(null)

  const send = async (text) => {
    const content = text || input.trim()
    if (!content) return
    setInput('')
    const newMsg = { role: 'user', content }
    setMessages(prev => [...prev, newMsg])
    setLoading(true)

    try {
      // demo_mode: false → real Groq API call
      const res = await sendChat([...messages, newMsg], appId, false)
      const cp = res.controlplane || {}
      const reply = res.choices?.[0]?.message?.content || '(no response)'
      setMessages(prev => [...prev, { role: 'assistant', content: reply, meta: cp }])
      setLastMeta(cp)
    } catch (e) {
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: 'Error contacting gateway. Make sure the backend is running on port 8000.',
        error: true,
      }])
    } finally {
      setLoading(false)
    }
  }

  const actionColor = (a) => ({
    allow: '#10b981', annotate: '#3b82f6', warn: '#f59e0b',
    redact: '#f97316', block: '#ef4444', escalate: '#8b5cf6',
  })[a] || '#8b9ab5'

  return (
    <div style={{ display: 'grid', gridTemplateColumns: '1fr 340px', gap: 16, height: 'calc(100vh - 120px)' }}>
      {/* Chat Panel */}
      <div className="card" style={{ display: 'flex', flexDirection: 'column', padding: 0, overflow: 'hidden' }}>
        <div style={{ padding: '14px 18px', borderBottom: '1px solid var(--border)', fontSize: 13, fontWeight: 600 }}>
          Live Gateway Test
          <span style={{ marginLeft: 10, fontSize: 11, color: 'var(--accent-green)', fontWeight: 500 }}>
          ● Real Groq API (openai/gpt-oss-20b)
          </span>
        </div>

        {/* Demo prompts */}
        <div style={{ display: 'flex', gap: 6, padding: '10px 14px', borderBottom: '1px solid var(--border)', flexWrap: 'wrap' }}>
          {DEMO_PROMPTS.map(p => (
            <button key={p.label} className="btn btn-ghost" style={{ fontSize: 11, padding: '4px 10px' }}
              onClick={() => send(p.text)}>
              {p.label}
            </button>
          ))}
        </div>

        {/* Messages */}
        <div style={{ flex: 1, overflowY: 'auto', padding: '16px', display: 'flex', flexDirection: 'column', gap: 12 }}>
          {messages.length === 0 && (
            <div className="empty-state" style={{ paddingTop: 80 }}>
              <Zap size={40} opacity={0.3} />
              <p style={{ marginTop: 12 }}>Try one of the demo prompts above to see ControlPlane in action.</p>
            </div>
          )}
          {messages.map((m, i) => (
            <div key={i} style={{ display: 'flex', flexDirection: 'column', alignItems: m.role === 'user' ? 'flex-end' : 'flex-start' }}>
              <div style={{
                maxWidth: '80%',
                padding: '10px 14px',
                borderRadius: m.role === 'user' ? '14px 14px 4px 14px' : '14px 14px 14px 4px',
                background: m.role === 'user' ? 'rgba(59,130,246,0.2)' : m.error ? 'rgba(239,68,68,0.1)' : 'var(--bg-elevated)',
                border: `1px solid ${m.role === 'user' ? 'rgba(59,130,246,0.35)' : 'var(--border)'}`,
                fontSize: 13, lineHeight: 1.65,
                whiteSpace: 'pre-wrap',
              }}>
                {m.content}
              </div>

              {/* ControlPlane metadata badge */}
              {m.meta && (
                <div style={{ display: 'flex', gap: 6, marginTop: 6, flexWrap: 'wrap', maxWidth: '80%' }}>
                  <span style={{
                    padding: '3px 8px', borderRadius: 99, fontSize: 10, fontWeight: 700,
                    background: `${actionColor(m.meta.policy_action)}22`,
                    color: actionColor(m.meta.policy_action),
                    border: `1px solid ${actionColor(m.meta.policy_action)}44`,
                  }}>
                    {m.meta.policy_action?.toUpperCase()}
                  </span>
                  <span style={{ fontSize: 10, color: 'var(--text-muted)', alignSelf: 'center' }}>
                    impact: <strong>{m.meta.impact}</strong>
                  </span>
                  {m.meta.fast_checks?.pii_detected && (
                    <span style={{ fontSize: 10, color: '#f97316' }}>🔒 PII detected</span>
                  )}
                  {m.meta.fast_checks?.credentials_detected && (
                    <span style={{ fontSize: 10, color: '#ef4444' }}>⚠ Credentials redacted</span>
                  )}
                  <span style={{ fontSize: 10, color: 'var(--text-muted)' }}>
                    {fmtCost(m.meta.cost_usd)} · {m.meta.latency_ms?.toFixed(0)}ms
                  </span>
                </div>
              )}
            </div>
          ))}
          {loading && (
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, color: 'var(--text-muted)', fontSize: 12 }}>
              <Loader size={14} className="spin" style={{ animation: 'spin 0.8s linear infinite' }} />
              ControlPlane processing…
            </div>
          )}
        </div>

        {/* Input */}
        <div style={{ padding: '12px 16px', borderTop: '1px solid var(--border)', display: 'flex', gap: 8 }}>
          <select value={appId} onChange={e => setAppId(e.target.value)}
            style={{ padding: '8px 10px', background: 'var(--bg-elevated)', border: '1px solid var(--border)', borderRadius: 6, color: 'var(--text-secondary)', fontSize: 12, flexShrink: 0 }}>
            {APP_IDS.map(a => <option key={a} value={a}>{a}</option>)}
          </select>
          <input
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && !e.shiftKey && send()}
            placeholder="Type a message… (Enter to send)"
            disabled={loading}
            style={{ flex: 1, padding: '8px 12px', background: 'var(--bg-elevated)', border: '1px solid var(--border)', borderRadius: 6, color: 'var(--text-primary)', fontSize: 13 }}
          />
          <button className="btn btn-primary" onClick={() => send()} disabled={loading || !input.trim()}>
            <Send size={14} />
          </button>
        </div>
      </div>

      {/* Meta Panel */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 12, overflowY: 'auto' }}>
        {lastMeta ? (
          <>
            <div className="card">
              <div className="card-title" style={{ marginBottom: 12 }}>Last Response Checks</div>
              {[
                { label: 'Policy Action', value: <span className={`badge badge-${lastMeta.policy_action}`}>{lastMeta.policy_action}</span> },
                { label: 'Impact', value: <span className={`badge badge-${lastMeta.impact}`}>{lastMeta.impact}</span> },
                { label: 'Prelim Impact', value: lastMeta.impact_preliminary },
                { label: 'Deep Check', value: lastMeta.deep_check_status },
              ].map(r => (
                <div key={r.label} className="detail-row">
                  <span className="detail-label">{r.label}</span>
                  <span className="detail-value">{r.value}</span>
                </div>
              ))}
            </div>

            <div className="card">
              <div className="card-title" style={{ marginBottom: 12 }}>
                <Shield size={13} style={{ display: 'inline', marginRight: 5 }} />Fast Checks
              </div>
              {Object.entries(lastMeta.fast_checks || {}).map(([k, v]) => (
                <div key={k} className="detail-row">
                  <span className="detail-label" style={{ fontSize: 11 }}>{k.replace(/_/g, ' ')}</span>
                  <span className="detail-value" style={{ fontSize: 11, color: typeof v === 'number' && v > 0.3 ? '#f97316' : 'var(--text-primary)' }}>
                    {typeof v === 'boolean' ? (v ? 'Yes' : 'No') : typeof v === 'number' ? fmtPct(v) : String(v)}
                  </span>
                </div>
              ))}
            </div>

            <div className="card">
              <div className="card-title" style={{ marginBottom: 12 }}>
                <DollarSign size={13} style={{ display: 'inline', marginRight: 5 }} />Performance
              </div>
              <div className="detail-row">
                <span className="detail-label">Cost</span>
                <span className="detail-value" style={{ color: '#10b981' }}>{fmtCost(lastMeta.cost_usd)}</span>
              </div>
              <div className="detail-row">
                <span className="detail-label">Latency</span>
                <span className="detail-value">{lastMeta.latency_ms?.toFixed(1)}ms</span>
              </div>
              <div className="detail-row">
                <span className="detail-label">Request ID</span>
                <span className="mono text-muted" style={{ fontSize: 10 }}>{lastMeta.request_id?.slice(0, 20)}…</span>
              </div>
            </div>

            {lastMeta.annotations?.length > 0 && (
              <div className="card">
                <div className="card-title" style={{ marginBottom: 10 }}>
                  <AlertTriangle size={13} style={{ display: 'inline', marginRight: 5 }} />Annotations
                </div>
                {lastMeta.annotations.map((a, i) => (
                  <div key={i} style={{ fontSize: 11, color: '#fcd34d', marginBottom: 6, padding: '6px 10px', background: 'rgba(245,158,11,0.08)', borderRadius: 6, borderLeft: '3px solid #f59e0b' }}>
                    {a}
                  </div>
                ))}
              </div>
            )}
          </>
        ) : (
          <div className="card">
            <div className="empty-state" style={{ padding: '40px 20px' }}>
              <Shield size={32} opacity={0.3} />
              <p style={{ marginTop: 10, fontSize: 12 }}>Send a message to see ControlPlane metadata here.</p>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
