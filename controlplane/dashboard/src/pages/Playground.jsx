import { useState } from 'react'
import { sendChat, invalidateCache } from '../api'
import { fmtCost, fmtPct } from '../utils'
import { Send, Loader, Zap, Shield, DollarSign, AlertTriangle, Trash2 } from 'lucide-react'

const DEMO_PROMPTS = [
  { label: '🔍 Hallucination',   text: 'Who invented the telephone?' },
  { label: '⚕ Medical Re-score', text: 'What herbs help with stress?' },
  { label: '🔑 Data Leakage',    text: 'My API key is sk-abc123testkey456789, can you help me use it in Python?' },
  { label: '📐 Math Claim',      text: 'What is 15% of 240?' },
  { label: '🗺 Factual',         text: 'What is the capital of France?' },
]

const APP_IDS = ['customer_support', 'internal_kb', 'decision_support', 'demo']

// ── Module-level state — survives navigation (component unmount/remount) ───────
let _messages = []
let _lastMeta = null
let _appId    = 'demo'

export default function Playground() {
  // Initialise from module state so history persists when you switch pages
  const [messages, _setMessages] = useState(_messages)
  const [lastMeta, _setLastMeta] = useState(_lastMeta)
  const [appId,    _setAppId]    = useState(_appId)
  const [input,    setInput]     = useState('')
  const [loading,  setLoading]   = useState(false)

  // Wrappers that keep module state in sync
  const setMessages = (v) => { const val = typeof v === 'function' ? v(_messages) : v; _messages = val; _setMessages(val) }
  const setLastMeta = (v) => { _lastMeta = v; _setLastMeta(v) }
  const setAppId    = (v) => { _appId    = v; _setAppId(v) }

  const clearHistory = () => { setMessages([]); setLastMeta(null) }

  const send = async (text) => {
    const content = text || input.trim()
    if (!content || loading) return
    setInput('')
    const newMsg = { role: 'user', content }
    setMessages(prev => [...prev, newMsg])
    setLoading(true)

    try {
      const res = await sendChat([...messages, newMsg], appId, false)
      const cp    = res.controlplane || {}
      const reply = res.choices?.[0]?.message?.content || '(no response)'
      setMessages(prev => [...prev, { role: 'assistant', content: reply, meta: cp }])
      setLastMeta(cp)

      // ── Invalidate all cached data so Event Log / Hallucination / etc.
      //    pick up the new event immediately on next visit ─────────────
      invalidateCache()

    } catch (err) {
      const errMsg = err.response?.data?.detail?.message || 'Error contacting gateway. Check that the backend is online.'
      const errCp = err.response?.data?.detail ? {
        policy_action: 'block',
        reason: err.response.data.detail.error,
        event_id: err.response.data.detail.request_id,
      } : null

      setMessages(prev => [...prev, {
        role: 'assistant',
        content: errMsg,
        error: true,
        meta: errCp
      }])
      if (errCp) setLastMeta(errCp)
    } finally {
      setLoading(false)
    }
  }

  const actionColor = (a) => ({
    allow: '#059669', annotate: '#2563eb', warn: '#d97706',
    redact: '#ea580c', block: '#dc2626', escalate: '#6b7280',
  })[a] || '#6b7280'

  return (
    <div style={{ display: 'grid', gridTemplateColumns: '1fr 340px', gap: 16, height: 'calc(100vh - 120px)' }}>

      {/* ── Chat Panel ── */}
      <div className="card" style={{ display: 'flex', flexDirection: 'column', padding: 0, overflow: 'hidden' }}>

        {/* Header */}
        <div style={{ padding: '12px 18px', borderBottom: '1px solid var(--border)', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div>
            <span style={{ fontSize: 13, fontWeight: 600 }}>Live Gateway Test</span>
            <span style={{ marginLeft: 10, fontSize: 11, color: 'var(--accent)', fontWeight: 500 }}>
              ● Groq API (openai/gpt-oss-20b)
            </span>
          </div>
          {messages.length > 0 && (
            <button className="btn btn-ghost" style={{ fontSize: 11, padding: '3px 8px', gap: 4 }}
              onClick={clearHistory} title="Clear history">
              <Trash2 size={12} /> Clear
            </button>
          )}
        </div>

        {/* Demo prompt chips */}
        <div style={{ display: 'flex', gap: 6, padding: '10px 14px', borderBottom: '1px solid var(--border)', flexWrap: 'wrap' }}>
          {DEMO_PROMPTS.map(p => (
            <button key={p.label} className="btn btn-ghost"
              style={{ fontSize: 11, padding: '4px 10px' }}
              onClick={() => send(p.text)}
              disabled={loading}>
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
              <p style={{ marginTop: 6, fontSize: 11, color: 'var(--text-muted)' }}>
                Your chat history is preserved when you switch pages.
              </p>
            </div>
          )}

          {messages.map((m, i) => (
            <div key={i} style={{ display: 'flex', flexDirection: 'column', alignItems: m.role === 'user' ? 'flex-end' : 'flex-start' }}>
              <div style={{
                maxWidth: '82%',
                padding: '10px 14px',
                borderRadius: m.role === 'user' ? '14px 14px 4px 14px' : '14px 14px 14px 4px',
                background: m.role === 'user'
                  ? 'var(--accent-muted)'
                  : m.error ? '#fef2f2' : 'var(--bg-elevated)',
                border: `1px solid ${m.role === 'user' ? 'rgba(79,70,229,0.20)' : m.error ? '#fecaca' : 'var(--border)'}`,
                fontSize: 13, lineHeight: 1.65,
                whiteSpace: 'pre-wrap',
                color: m.error ? '#b91c1c' : 'var(--text-primary)',
              }}>
                {m.content}
              </div>

              {/* ControlPlane metadata */}
              {m.meta && (
                <div style={{ display: 'flex', gap: 6, marginTop: 6, flexWrap: 'wrap', maxWidth: '82%' }}>
                  <span style={{
                    padding: '3px 8px', borderRadius: 99, fontSize: 10, fontWeight: 700,
                    background: `${actionColor(m.meta.policy_action)}1a`,
                    color: actionColor(m.meta.policy_action),
                    border: `1px solid ${actionColor(m.meta.policy_action)}44`,
                  }}>
                    {m.meta.policy_action?.toUpperCase()}
                  </span>
                  <span style={{ fontSize: 10, color: 'var(--text-muted)', alignSelf: 'center' }}>
                    impact: <strong style={{ color: 'var(--text-secondary)' }}>{m.meta.impact}</strong>
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
              <Loader size={14} style={{ animation: 'spin 0.8s linear infinite' }} />
              ControlPlane processing…
            </div>
          )}
        </div>

        {/* Input row */}
        <div style={{ padding: '12px 16px', borderTop: '1px solid var(--border)', display: 'flex', gap: 8 }}>
          <select value={appId} onChange={e => setAppId(e.target.value)}
            style={{ padding: '8px 10px', borderRadius: 6, fontSize: 12, flexShrink: 0 }}>
            {APP_IDS.map(a => <option key={a} value={a}>{a}</option>)}
          </select>
          <input
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && !e.shiftKey && send()}
            placeholder="Type a message… (Enter to send)"
            disabled={loading}
            style={{ flex: 1, padding: '8px 12px', borderRadius: 6, fontSize: 13 }}
          />
          <button className="btn btn-primary" onClick={() => send()} disabled={loading || !input.trim()}>
            <Send size={14} />
          </button>
        </div>
      </div>

      {/* ── Meta Panel ── */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 12, overflowY: 'auto' }}>
        {lastMeta ? (
          <>
            <div className="card">
              <div className="card-title" style={{ marginBottom: 12 }}>Last Response Checks</div>
              {[
                { label: 'Policy Action',  value: <span className={`badge badge-${lastMeta.policy_action}`}>{lastMeta.policy_action}</span> },
                { label: 'Impact',         value: <span className={`badge badge-${lastMeta.impact}`}>{lastMeta.impact}</span> },
                { label: 'Prelim Impact',  value: lastMeta.impact_preliminary },
                { label: 'Deep Check',     value: lastMeta.deep_check_status },
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
                <span className="detail-value" style={{ color: 'var(--accent)' }}>{fmtCost(lastMeta.cost_usd)}</span>
              </div>
              <div className="detail-row">
                <span className="detail-label">Latency</span>
                <span className="detail-value">{lastMeta.latency_ms?.toFixed(1)}ms</span>
              </div>
              <div className="detail-row">
                <span className="detail-label">Request ID</span>
                <span className="mono text-muted" style={{ fontSize: 10 }}>{lastMeta.request_id?.slice(0, 22)}…</span>
              </div>
            </div>

            {lastMeta.annotations?.length > 0 && (
              <div className="card">
                <div className="card-title" style={{ marginBottom: 10 }}>
                  <AlertTriangle size={13} style={{ display: 'inline', marginRight: 5 }} />Annotations
                </div>
                {lastMeta.annotations.map((a, i) => (
                  <div key={i} style={{ fontSize: 11, color: '#92400e', marginBottom: 6, padding: '6px 10px', background: '#fffbeb', borderRadius: 6, borderLeft: '3px solid #f59e0b' }}>
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
