import { useState, useEffect } from 'react'
import { LayoutDashboard, Zap, DollarSign, Shield, Users, Activity, Terminal } from 'lucide-react'
import Overview from './pages/Overview'
import EventLog from './pages/EventLog'
import EventDetail from './pages/EventDetail'
import HallucinationRate from './pages/HallucinationRate'
import CostAnalytics from './pages/CostAnalytics'
import ReviewQueue from './pages/ReviewQueue'
import Playground from './pages/Playground'
import { startKeepAlive, getOverview, getEvents, getHallucinationMetrics, getCostMetrics } from './api'

const NAV = [
  { id: 'playground',   label: 'Live Demo',        icon: Terminal },
  { id: 'overview',      label: 'Overview',        icon: LayoutDashboard },
  { id: 'events',        label: 'Event Log',        icon: Activity },
  { id: 'hallucination', label: 'Hallucination',    icon: Zap },
  { id: 'cost',          label: 'Cost Analytics',   icon: DollarSign },
  { id: 'pii',           label: 'Data Safety',      icon: Shield },
  { id: 'review',        label: 'Review Queue',     icon: Users },
]

export default function App() {
  const [page, setPage]         = useState('playground')
  const [selectedEvent, setSelectedEvent] = useState(null)

  useEffect(() => {
    // Wake up Render immediately + keep alive every 10 min
    startKeepAlive()
    // Prefetch common pages so navigation is instant
    getOverview().catch(() => {})
    getEvents({ limit: 20 }).catch(() => {})
    getHallucinationMetrics().catch(() => {})
    getCostMetrics().catch(() => {})
  }, [])


  function navigate(id) { setPage(id); setSelectedEvent(null) }
  function openEvent(ev) { setSelectedEvent(ev); setPage('event-detail') }
  function backToEvents() { setSelectedEvent(null); setPage('events') }

  const pageTitle = {
    'overview': 'Fleet Overview',
    'events': 'Event Log',
    'event-detail': 'Request Detail',
    'hallucination': 'Hallucination Monitor',
    'cost': 'Cost Analytics',
    'pii': 'Data Safety',
    'review': 'Review Queue',
    'playground': 'Live Demo',
  }[page] || 'ControlPlane'

  return (
    <div className="app-shell">
      {/* Sidebar */}
      <nav className="sidebar">
        <div className="sidebar-logo">
          <h1>ControlPlane</h1>
          <span>Responsible AI Gateway</span>
        </div>
        <div className="sidebar-nav">
          <div className="nav-section-label">Demo</div>
          {NAV.slice(0, 1).map(({ id, label, icon: Icon }) => (
            <div
              key={id}
              className={`nav-item${page === id ? ' active' : ''}`}
              onClick={() => navigate(id)}
            >
              <Icon size={16} />
              {label}
            </div>
          ))}
          <div className="nav-section-label" style={{ marginTop: 8 }}>Monitor</div>
          {NAV.slice(1, 6).map(({ id, label, icon: Icon }) => (
            <div
              key={id}
              className={`nav-item${page === id ? ' active' : ''}`}
              onClick={() => navigate(id)}
            >
              <Icon size={16} />
              {label}
            </div>
          ))}
          <div className="nav-section-label" style={{ marginTop: 8 }}>Manage</div>
          {NAV.slice(6).map(({ id, label, icon: Icon }) => (
            <div
              key={id}
              className={`nav-item${page === id ? ' active' : ''}`}
              onClick={() => navigate(id)}
            >
              <Icon size={16} />
              {label}
            </div>
          ))}
        </div>
        <div style={{ padding: '12px 18px', borderTop: '1px solid var(--border)', fontSize: 11, color: 'var(--text-muted)' }}>
          v0.2.0 · AIC 2026
        </div>
      </nav>

      {/* Main */}
      <div className="main-content">
        <div className="topbar">
          <div>
            <div className="topbar-title">{pageTitle}</div>
          </div>
          <div className="topbar-right">
            <div className="status-dot" />
            <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>Gateway Online</span>
          </div>
        </div>

        <div className="page-content">
          {page === 'overview'      && <Overview onEventClick={openEvent} />}
          {page === 'events'        && <EventLog onEventClick={openEvent} />}
          {page === 'event-detail'  && <EventDetail event={selectedEvent} onBack={backToEvents} />}
          {page === 'hallucination' && <HallucinationRate />}
          {page === 'cost'          && <CostAnalytics />}
          {page === 'pii'           && <EventLog filter="pii" onEventClick={openEvent} />}
          {page === 'review'        && <ReviewQueue onEventClick={openEvent} />}
          {page === 'playground'    && <Playground />}
        </div>
      </div>
    </div>
  )
}
