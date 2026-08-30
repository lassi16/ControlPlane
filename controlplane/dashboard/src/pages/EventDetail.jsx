import { useEffect, useState } from 'react'
import { getEventDetail } from '../api'
import { fmtCost, fmtPct, fmtTs, riskColor, CLAIM_STATUS_COLORS } from '../utils'
import { ArrowLeft, RefreshCw, Shield, Zap, Eye, Lock, AlertTriangle, CheckCircle, XCircle, HelpCircle, FileText, Clock, DollarSign, Activity, Search } from 'lucide-react'

/* ── Helpers ── */
function ScoreBar({ label, score, thresholds = [0.3, 0.6] }) {
  const pct = Math.min((score || 0) * 100, 100)
  const color = score > thresholds[1] ? '#ef4444' : score > thresholds[0] ? '#f59e0b' : '#10b981'
  return (
    <div className="audit-score-row">
      <span className="audit-score-label">{label}</span>
      <div className="audit-score-bar-track">
        <div className="audit-score-bar-fill" style={{ width: `${pct}%`, background: color }} />
      </div>
      <span className="audit-score-value" style={{ color }}>{fmtPct(score)}</span>
    </div>
  )
}

function StatusIcon({ ok }) {
  return ok
    ? <CheckCircle size={14} color="#10b981" />
    : <XCircle size={14} color="#ef4444" />
}

function AuditSection({ icon: Icon, title, children, variant }) {
  return (
    <div className={`audit-section ${variant || ''}`}>
      <div className="audit-section-header">
        {Icon && <Icon size={15} />}
        <span>{title}</span>
      </div>
      <div className="audit-section-body">
        {children}
      </div>
    </div>
  )
}

/* ── Main Component ── */
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
  const actionDetails = detail.action_details || {}
  const lineage = detail.lineage || {}
  const inputPii = detail.input_pii || []

  const verdictColor = {
    allow: '#10b981', annotate: '#3b82f6', warn: '#f59e0b',
    redact: '#f97316', block: '#ef4444', escalate: '#6b7280',
  }[detail.policy_action] || '#6b7280'

  return (
    <div className="audit-report">

      {/* ── Navigation ── */}
      <div className="audit-nav">
        <button className="btn btn-ghost" onClick={onBack}><ArrowLeft size={14} /> Back to Event Log</button>
        <button className="btn btn-ghost" onClick={refresh} disabled={loading}><RefreshCw size={14} /> Refresh</button>
      </div>

      {/* ═══════════════════════════════════════════════════════════
          SECTION 1 — Report Header
          ═══════════════════════════════════════════════════════════ */}
      <div className="audit-header">
        <div className="audit-header-left">
          <div className="audit-header-title">
            <FileText size={20} style={{ color: 'var(--accent)' }} />
            <h2>Audit Report</h2>
          </div>
          <div className="audit-header-meta">
            <span><Clock size={12} /> {detail.timestamp ? new Date(detail.timestamp * 1000).toLocaleString() : '—'}</span>
            <span className="audit-divider">|</span>
            <span className="mono" style={{ fontSize: 11 }}>{detail.request_id}</span>
          </div>
        </div>
        <div className="audit-verdict" style={{ '--verdict-color': verdictColor }}>
          <span className="audit-verdict-label">VERDICT</span>
          <span className="audit-verdict-value">{detail.policy_action?.toUpperCase()}</span>
        </div>
      </div>

      {/* ── Quick info strip ── */}
      <div className="audit-info-strip">
        {[
          { label: 'Application', value: detail.application_id },
          { label: 'Model', value: detail.model_id },
          { label: 'Impact', value: detail.impact_rescored?.toUpperCase(), className: `badge badge-${detail.impact_rescored}` },
          { label: 'Cost', value: fmtCost(detail.actual_cost) },
          { label: 'Latency', value: detail.latency_ms ? `${detail.latency_ms.toFixed(0)}ms` : '—' },
          { label: 'Tokens', value: `${detail.input_tokens || 0} in / ${detail.output_tokens || 0} out` },
        ].map(item => (
          <div key={item.label} className="audit-info-item">
            <span className="audit-info-label">{item.label}</span>
            {item.className
              ? <span className={item.className} style={{ fontSize: 11 }}>{item.value}</span>
              : <span className="audit-info-value">{item.value}</span>
            }
          </div>
        ))}
      </div>

      {/* ═══════════════════════════════════════════════════════════
          SECTION 2 — Conversation
          ═══════════════════════════════════════════════════════════ */}
      <AuditSection icon={Activity} title="Conversation">
        <div className="audit-conversation">
          <div className="audit-msg audit-msg-user">
            <div className="audit-msg-role">USER</div>
            <div className="audit-msg-content">{detail.user_query || '—'}</div>
          </div>
          <div className="audit-msg audit-msg-assistant">
            <div className="audit-msg-role">LLM RESPONSE</div>
            <div className="audit-msg-content">{detail.llm_response || '—'}</div>
          </div>
        </div>
      </AuditSection>

      {/* ═══════════════════════════════════════════════════════════
          SECTION 3 — Input Checks (Pre-Flight)
          ═══════════════════════════════════════════════════════════ */}
      <AuditSection icon={Shield} title="Pre-Flight Checks (Input)">
        <div className="audit-checks-grid">
          {/* Injection Detection */}
          <div className="audit-check-card">
            <div className="audit-check-title">
              <StatusIcon ok={(detail.injection_score || 0) < 0.55} />
              Prompt Injection
            </div>
            <ScoreBar label="Injection Score" score={detail.injection_score} thresholds={[0.3, 0.55]} />
            <div className="audit-check-detail">
              {(detail.injection_score || 0) >= 0.55
                ? <span style={{ color: '#ef4444', fontSize: 12 }}>⚠ Would be blocked at this threshold</span>
                : <span style={{ color: '#10b981', fontSize: 12 }}>✓ No injection patterns detected</span>
              }
            </div>
          </div>


          {/* Input PII */}
          <div className="audit-check-card">
            <div className="audit-check-title">
              <StatusIcon ok={inputPii.length === 0} />
              PII in Input
            </div>
            {inputPii.length > 0 ? (
              <div className="audit-check-detail">
                <span style={{ fontSize: 12, color: '#f97316' }}>
                  Found {inputPii.length} PII item(s): {inputPii.map(p => p.type || p).join(', ')}
                </span>
              </div>
            ) : (
              <div className="audit-check-detail">
                <span style={{ color: '#10b981', fontSize: 12 }}>✓ No PII detected in user input</span>
              </div>
            )}
          </div>

          {/* Query Classification */}
          <div className="audit-check-card">
            <div className="audit-check-title">
              <Search size={14} color="var(--accent)" />
              Query Classification
            </div>
            <div className="audit-check-detail">
              {(detail.query_labels || []).length > 0 ? (
                <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                  {detail.query_labels.map((l, i) => (
                    <span key={i} className="badge" style={{ background: 'var(--accent-muted)', color: 'var(--accent)', border: '1px solid var(--border-glow)', fontSize: 10 }}>{l}</span>
                  ))}
                </div>
              ) : (
                <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>general</span>
              )}
            </div>
          </div>

          {/* Impact Scoring */}
          <div className="audit-check-card">
            <div className="audit-check-title">
              <Zap size={14} color="var(--accent)" />
              Impact Assessment
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 4 }}>
              <span className={`badge badge-${detail.impact_preliminary}`}>{detail.impact_preliminary}</span>
              <span style={{ color: 'var(--text-muted)', fontSize: 12 }}>→</span>
              <span className={`badge badge-${detail.impact_rescored}`}>{detail.impact_rescored}</span>
              {detail.impact_preliminary !== detail.impact_rescored && (
                <span style={{ fontSize: 11, color: '#f97316', fontWeight: 600 }}>RE-SCORED</span>
              )}
            </div>
          </div>
        </div>
      </AuditSection>

      {/* ═══════════════════════════════════════════════════════════
          SECTION 4 — Output Checks (Post-Flight)
          ═══════════════════════════════════════════════════════════ */}
      <AuditSection icon={Eye} title="Post-Flight Checks (Output)">
        <div className="audit-checks-grid">
          {/* PII in Output */}
          <div className="audit-check-card">
            <div className="audit-check-title">
              <StatusIcon ok={!tier1.pii_detected} />
              PII in Response
            </div>
            <div className="audit-check-detail">
              {tier1.pii_detected ? (
                <span style={{ color: '#ef4444', fontSize: 12 }}>
                  ⚠ {tier1.detection_count || 'Multiple'} PII entities detected
                  {tier1.detections?.length > 0 && (
                    <span style={{ display: 'block', marginTop: 4, color: '#b91c1c' }}>
                      Types: {tier1.detections.map(d => d.type).join(', ')}
                    </span>
                  )}
                </span>
              ) : (
                <span style={{ color: '#10b981', fontSize: 12 }}>✓ No PII in response</span>
              )}
            </div>
          </div>

          {/* Credentials */}
          <div className="audit-check-card">
            <div className="audit-check-title">
              <StatusIcon ok={!tier1.credentials_detected} />
              Credentials / Secrets
            </div>
            <div className="audit-check-detail">
              {tier1.credentials_detected ? (
                <span style={{ color: '#ef4444', fontSize: 12 }}>⚠ API keys or credentials detected — auto-redacted</span>
              ) : (
                <span style={{ color: '#10b981', fontSize: 12 }}>✓ No credentials in response</span>
              )}
            </div>
          </div>


          {/* Confidence */}
          <div className="audit-check-card">
            <div className="audit-check-title">
              <CheckCircle size={14} color="var(--accent)" />
              Response Confidence
            </div>
            <ScoreBar label="Confidence" score={detail.confidence_score} thresholds={[0.3, 0.6]} />
          </div>

          {/* Data Lineage */}
          <div className="audit-check-card">
            <div className="audit-check-title">
              <StatusIcon ok={!lineage.leaked} />
              Data Lineage
            </div>
            <div className="audit-check-detail">
              {lineage.leaked ? (
                <span style={{ color: '#ef4444', fontSize: 12 }}>
                  ⚠ Data leakage detected (severity: {lineage.severity})
                  {lineage.summary && <span style={{ display: 'block', marginTop: 4 }}>{lineage.summary}</span>}
                </span>
              ) : (
                <span style={{ color: '#10b981', fontSize: 12 }}>✓ No data leakage detected</span>
              )}
            </div>
          </div>
        </div>
      </AuditSection>

      {/* ═══════════════════════════════════════════════════════════
          SECTION 5 — Deep Verification (if applicable)
          ═══════════════════════════════════════════════════════════ */}
      <AuditSection icon={Zap} title={`Deep Verification — ${claims.length > 0 ? claims.length + ' Claims Extracted' : detail.deep_check_status || 'Not Run'}`}>
        {claims.length > 0 ? (
          <>
            {/* Risk summary cards */}
            {detail.risk_score != null && (
              <div className="audit-risk-summary">
                {[
                  { label: 'Risk Score', value: fmtPct(detail.risk_score), color: riskColor(detail.risk_score) },
                  { label: 'Contradiction Rate', value: fmtPct(detail.contradiction_rate), color: (detail.contradiction_rate || 0) > 0.3 ? '#ef4444' : '#10b981' },
                  { label: 'Groundedness', value: fmtPct(detail.groundedness_score), color: '#10b981' },
                  { label: 'Coverage', value: fmtPct(detail.verification_coverage), color: '#3b82f6' },
                ].map(m => (
                  <div key={m.label} className="audit-risk-card">
                    <div className="audit-risk-value" style={{ color: m.color }}>{m.value}</div>
                    <div className="audit-risk-label">{m.label}</div>
                  </div>
                ))}
              </div>
            )}

            {/* Claims list */}
            <div className="audit-claims">
              {claims.map((c, i) => {
                const statusColor = CLAIM_STATUS_COLORS[c.status] || '#6b7280'
                return (
                  <div key={i} className="audit-claim" style={{ display: 'flex', flexDirection: 'column', gap: 12, padding: 16 }}>
                    
                    {/* Step 1: Claim */}
                    <div style={{ display: 'flex', gap: 12 }}>
                      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
                        <div style={{ width: 10, height: 10, borderRadius: '50%', background: 'var(--accent)' }} />
                        <div style={{ width: 2, flex: 1, background: 'var(--border)' }} />
                      </div>
                      <div style={{ paddingBottom: 12 }}>
                        <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: 1, marginBottom: 4 }}>1. Extract Claim</div>
                        <div className="audit-claim-text" style={{ fontSize: 14 }}>"{c.text}"</div>
                      </div>
                    </div>

                    {/* Step 2: Evidence */}
                    <div style={{ display: 'flex', gap: 12 }}>
                      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
                        <div style={{ width: 10, height: 10, borderRadius: '50%', background: '#8b5cf6' }} />
                        <div style={{ width: 2, flex: 1, background: 'var(--border)' }} />
                      </div>
                      <div style={{ paddingBottom: 12 }}>
                        <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: 1, marginBottom: 4 }}>2. Retrieve Evidence</div>
                        <div className="audit-claim-evidence" style={{ fontSize: 13, color: 'var(--text-secondary)' }}>
                          {c.evidence?.length > 0 ? (
                            <>
                              "{c.evidence[0].snippet?.slice(0, 150)}…"
                              {c.evidence[0].title && <span className="audit-claim-source" style={{ color: 'var(--text-muted)' }}> — {c.evidence[0].title}</span>}
                            </>
                          ) : (
                            <span style={{ fontStyle: 'italic' }}>No external evidence found.</span>
                          )}
                        </div>
                      </div>
                    </div>

                    {/* Step 3: Verdict */}
                    <div style={{ display: 'flex', gap: 12 }}>
                      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
                        <div style={{ width: 10, height: 10, borderRadius: '50%', background: statusColor }} />
                      </div>
                      <div>
                        <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: 1, marginBottom: 4 }}>3. NLI Verdict</div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                          <span className={`badge badge-${(c.status || 'pending').toLowerCase()}`}>{c.status || 'pending'}</span>
                          {c.nli_confidence > 0 && (
                            <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>Confidence: {fmtPct(c.nli_confidence)}</span>
                          )}
                        </div>
                      </div>
                    </div>
                  </div>
                )
              })}
            </div>
          </>
        ) : (
          <div style={{ padding: 20, textAlign: 'center', color: 'var(--text-muted)', fontSize: 13 }}>
            {detail.deep_check_status === 'complete'
              ? 'Deep check completed — no claims extracted.'
              : detail.deep_check_status === 'pending' || detail.deep_check_status === 'queued'
                ? '⏳ Deep verification is queued and will run asynchronously.'
                : 'Deep verification was not triggered for this request.'}
          </div>
        )}
      </AuditSection>

      {/* ═══════════════════════════════════════════════════════════
          SECTION 6 — Policy Decision
          ═══════════════════════════════════════════════════════════ */}
      <AuditSection icon={Shield} title="Policy Decision" variant="highlight">
        <div className="audit-policy-grid">
          <div className="audit-policy-main">
            <div className="audit-policy-verdict" style={{ '--verdict-color': verdictColor }}>
              <span style={{ fontSize: 11, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: 1 }}>Final Action</span>
              <span style={{ fontSize: 26, fontWeight: 800, color: verdictColor }}>{detail.policy_action?.toUpperCase()}</span>
            </div>
            <div className="audit-policy-sub-decisions">
              {[
                { label: 'Responsibility', value: actionDetails.responsibility_action },
                { label: 'Data Lineage', value: actionDetails.lineage_action },
                { label: 'Performance', value: actionDetails.performance_action },
                { label: 'Cost', value: actionDetails.cost_action },
              ].filter(d => d.value).map(d => (
                <div key={d.label} className="audit-sub-decision">
                  <span className="audit-sub-label">{d.label}</span>
                  <span className={`badge badge-${d.value}`} style={{ fontSize: 10 }}>{d.value}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Annotations */}
          {(actionDetails.annotations || detail.annotations || []).length > 0 && (
            <div className="audit-annotations">
              <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-secondary)', marginBottom: 8 }}>
                <AlertTriangle size={13} style={{ display: 'inline', marginRight: 5 }} />
                Annotations & Warnings
              </div>
              {(actionDetails.annotations || detail.annotations || []).map((a, i) => (
                <div key={i} className="audit-annotation">{a}</div>
              ))}
            </div>
          )}

          {/* Reasoning */}
          {actionDetails.reasoning && (
            <div style={{ marginTop: 12 }}>
              <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-secondary)', marginBottom: 6 }}>Reasoning</div>
              <div className="mono" style={{ fontSize: 11, color: 'var(--text-muted)', padding: '10px 14px', background: 'var(--bg-elevated)', borderRadius: 8, lineHeight: 1.8 }}>
                {actionDetails.reasoning}
              </div>
            </div>
          )}
        </div>
      </AuditSection>
    </div>
  )
}
