import { useEffect, useState } from 'react'
import { getEventDetail } from '../api'
import { fmtCost, fmtPct, fmtTs, riskColor, CLAIM_STATUS_COLORS } from '../utils'
import { ArrowLeft, RefreshCw } from 'lucide-react'

export default function EventDetail({ event, onBack }) {
  const [detail, setDetail] = useState(event)
  const [loading, setLoading] = useState(false)

  const refresh = () => {
    if (!event?.id) return
    setLoading(true)
    getEventDetail(event.id).then(setDetail).catch(console.error).finally(() => setLoading(false))
  }

  useEffect(() => { refresh() }, [event?.id])

  if (!detail) return <div className="empty-state">No event selected.</div>

  const claims = detail.claims || []
  const tier1  = detail.tier1_pii || {}
  const rc     = detail.contradiction_rate

  return (
    <div>
      <div style={{ display: 'flex', gap: 10, marginBottom: 18, alignItems: 'center' }}>
        <button className="btn btn-ghost" onClick={onBack}><ArrowLeft size={14} /> Back</button>
        <button className="btn btn-ghost" onClick={refresh} disabled={loading}><RefreshCw size={14} /> Refresh</button>
        <span className="mono text-muted" style={{ fontSize: 11 }}>{detail.request_id}</span>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginBottom: 16 }}>
        {/* Request info */}
        <div className="card">
          <div className="card-title" style={{ marginBottom: 12 }}>Request</div>
          <div className="detail-row"><span className="detail-label">Application</span><span className="detail-value">{detail.application_id}</span></div>
          <div className="detail-row"><span className="detail-label">Model</span><span className="detail-value mono">{detail.model_id}</span></div>
          <div className="detail-row"><span className="detail-label">Time</span><span className="detail-value">{fmtTs(detail.timestamp)}</span></div>
          <div className="detail-row"><span className="detail-label">Input Tokens</span><span className="detail-value">{detail.input_tokens}</span></div>
          <div className="detail-row"><span className="detail-label">Output Tokens</span><span className="detail-value">{detail.output_tokens}</span></div>
          <div className="detail-row"><span className="detail-label">Cost</span><span className="detail-value">{fmtCost(detail.actual_cost)}</span></div>
          <div className="detail-row"><span className="detail-label">Impact (prelim → final)</span>
            <span className="detail-value">
              <span className={`badge badge-${detail.impact_preliminary}`}>{detail.impact_preliminary}</span>
              {' → '}
              <span className={`badge badge-${detail.impact_rescored}`}>{detail.impact_rescored}</span>
            </span>
          </div>
        </div>

        {/* Policy decision */}
        <div className="card">
          <div className="card-title" style={{ marginBottom: 12 }}>Policy Decision</div>
          <div style={{ marginBottom: 12 }}>
            <span className={`badge badge-${detail.policy_action}`} style={{ fontSize: 14, padding: '5px 14px' }}>{detail.policy_action?.toUpperCase()}</span>
          </div>
          <div className="detail-row"><span className="detail-label">Injection Score</span><span className="detail-value">{fmtPct(detail.injection_score)}</span></div>
          <div className="detail-row"><span className="detail-label">Toxicity</span><span className="detail-value">{fmtPct(detail.tier2_toxicity)}</span></div>
          <div className="detail-row"><span className="detail-label">Confidence</span><span className="detail-value">{fmtPct(detail.confidence_score)}</span></div>
          <div className="detail-row"><span className="detail-label">PII Detected</span>
            <span className="detail-value" style={{ color: tier1.pii_detected ? 'var(--accent-red)' : 'var(--accent-green)' }}>
              {tier1.pii_detected ? 'Yes' : 'No'}
            </span>
          </div>
          <div className="detail-row"><span className="detail-label">Credentials</span>
            <span className="detail-value" style={{ color: tier1.credentials_detected ? 'var(--accent-red)' : 'var(--accent-green)' }}>
              {tier1.credentials_detected ? 'Detected' : 'None'}
            </span>
          </div>
          <div className="detail-row"><span className="detail-label">Deep Check</span>
            <span className="detail-value">
              <span style={{ padding: '2px 8px', borderRadius: 4, fontSize: 11,
                background: detail.deep_check_status === 'complete' ? 'rgba(16,185,129,0.1)' : 'rgba(245,158,11,0.1)',
                color: detail.deep_check_status === 'complete' ? '#10b981' : '#f59e0b',
              }}>{detail.deep_check_status}</span>
            </span>
          </div>
        </div>
      </div>

      {/* Query / Response */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginBottom: 16 }}>
        <div className="card">
          <div className="card-title" style={{ marginBottom: 8 }}>User Query</div>
          <div style={{ fontSize: 13, lineHeight: 1.7, color: 'var(--text-primary)', whiteSpace: 'pre-wrap' }}>
            {detail.user_query || '—'}
          </div>
        </div>
        <div className="card">
          <div className="card-title" style={{ marginBottom: 8 }}>LLM Response</div>
          <div style={{ fontSize: 13, lineHeight: 1.7, color: 'var(--text-primary)', whiteSpace: 'pre-wrap' }}>
            {detail.llm_response || '—'}
          </div>
        </div>
      </div>

      {/* Claims */}
      {claims.length > 0 && (
        <div className="card" style={{ marginBottom: 16 }}>
          <div className="card-header">
            <div className="card-title">Extracted Claims ({claims.length})</div>
            {rc != null && (
              <div style={{ fontSize: 12, color: rc > 0.3 ? 'var(--accent-red)' : 'var(--text-muted)' }}>
                Contradiction Rate: {fmtPct(rc)}
              </div>
            )}
          </div>
          {claims.map((c, i) => (
            <div key={i} className="claim-card">
              <div className="claim-text">{c.text}</div>
              <div className="claim-meta">
                <span className={`badge badge-${(c.status || 'pending').toLowerCase()}`}>{c.status || 'pending'}</span>
                <span className="badge" style={{ background: 'rgba(75,85,99,0.2)', color: 'var(--text-muted)' }}>{c.type}</span>
                {c.nli_confidence > 0 && (
                  <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>confidence: {fmtPct(c.nli_confidence)}</span>
                )}
              </div>
              {c.evidence?.length > 0 && (
                <div style={{ marginTop: 8, padding: '8px 10px', background: 'var(--bg-base)', borderRadius: 6, fontSize: 12, color: 'var(--text-muted)' }}>
                  <strong style={{ color: 'var(--text-secondary)' }}>Evidence:</strong> {c.evidence[0].snippet?.slice(0, 160)}…
                  <span style={{ marginLeft: 6, color: 'var(--accent-blue)', fontSize: 11 }}>{c.evidence[0].title}</span>
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Risk Score */}
      {detail.risk_score != null && (
        <div className="card">
          <div className="card-title" style={{ marginBottom: 12 }}>Risk Summary</div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4,1fr)', gap: 12 }}>
            {[
              { label: 'Risk Score', value: fmtPct(detail.risk_score), color: riskColor(detail.risk_score) },
              { label: 'Contradiction Rate', value: fmtPct(detail.contradiction_rate), color: '#f97316' },
              { label: 'Groundedness', value: fmtPct(detail.groundedness_score), color: '#10b981' },
              { label: 'Coverage', value: fmtPct(detail.verification_coverage), color: '#3b82f6' },
            ].map(m => (
              <div key={m.label} style={{ textAlign: 'center', padding: '14px', background: 'var(--bg-elevated)', borderRadius: 10 }}>
                <div style={{ fontSize: 22, fontWeight: 800, color: m.color }}>{m.value}</div>
                <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 4 }}>{m.label}</div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
