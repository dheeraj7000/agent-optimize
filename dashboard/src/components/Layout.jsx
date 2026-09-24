import { NavLink, Outlet, useLocation } from 'react-router-dom'
import {
  Activity, ArrowUpRight, BadgeCheck, Bot, ChartNoAxesCombined,
  ChevronDown, CircleDollarSign, Command, LayoutDashboard, ListChecks,
  Menu, Search, ShieldCheck, Zap,
} from 'lucide-react'

const nav = [
  { to: '/', icon: LayoutDashboard, label: 'Overview', group: 'Workspace' },
  { to: '/recommendations', icon: ListChecks, label: 'Recommendations', group: 'Workspace' },
  { to: '/traces', icon: Activity, label: 'Trace explorer', group: 'Observe' },
  { to: '/validation', icon: ShieldCheck, label: 'Validation', group: 'Observe' },
  { to: '/autopilot', icon: Bot, label: 'Autopilot', group: 'Operate' },
]

const titles = {
  '/': ['Overview', 'Spend intelligence for your AI systems'],
  '/recommendations': ['Recommendations', 'Prioritize savings with quality evidence'],
  '/traces': ['Trace explorer', 'Inspect cost, latency, and agent behavior'],
  '/validation': ['Validation', 'Prove savings without compromising quality'],
  '/autopilot': ['Autopilot', 'Operate within your quality and risk guardrails'],
}

function SidebarLink({ to, icon: Icon, label }) {
  return <NavLink to={to} end={to === '/'} className={({ isActive }) =>
    `nav-link ${isActive ? 'nav-link-active' : ''}`}>
    <Icon size={17} strokeWidth={1.8} />
    <span>{label}</span>
    {to === '/autopilot' && <span className="nav-status-dot" aria-label="Autopilot status" />}
  </NavLink>
}

export default function Layout() {
  const location = useLocation()
  const [pageTitle, pageDescription] = titles[location.pathname] || ['AgentOptimize', 'AI agent cost intelligence']
  const groups = [...new Set(nav.map((item) => item.group))]

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <a href="/" className="brand-lockup" aria-label="AgentOptimize home">
          <span className="brand-mark"><ChartNoAxesCombined size={19} strokeWidth={2.2} /></span>
          <span className="brand-wordmark">agent<span>optimize</span></span>
        </a>
        <div className="workspace-switcher">
          <span className="workspace-monogram">AO</span>
          <span className="workspace-copy"><strong>Agent workspace</strong><small>Production environment</small></span>
          <ChevronDown size={15} className="muted-icon" />
        </div>
        <nav className="sidebar-nav" aria-label="Main navigation">
          {groups.map((group) => <div className="nav-group" key={group}>
            <p className="nav-heading">{group}</p>
            {nav.filter((item) => item.group === group).map((item) => <SidebarLink key={item.to} {...item} />)}
          </div>)}
        </nav>
        <div className="sidebar-bottom">
          <div className="plan-card">
            <div className="plan-card-icon"><CircleDollarSign size={16} /></div>
            <div><strong>AI FinOps</strong><span>Cost · quality · reliability</span></div>
            <ArrowUpRight size={14} className="muted-icon" />
          </div>
          <div className="user-row">
            <div className="avatar">AO</div>
            <div className="user-copy"><strong>Workspace admin</strong><span>Owner access</span></div>
            <Menu size={16} className="muted-icon" />
          </div>
        </div>
      </aside>

      <main className="main-panel">
        <header className="topbar">
          <div className="breadcrumb"><span>Workspace</span><span className="breadcrumb-slash">/</span><strong>{pageTitle}</strong></div>
          <div className="topbar-actions">
            <div className="system-state"><span className="live-dot" /> All systems operational</div>
            <button type="button" className="icon-button" aria-label="Search"><Search size={17} /><kbd><Command size={11} /> K</kbd></button>
            <button type="button" className="avatar topbar-avatar" aria-label="Account">AO</button>
          </div>
        </header>
        <div className="page-wrap">
          <div className="page-heading">
            <div><div className="eyebrow"><Zap size={12} /> AI AGENT FINOPS</div><h1>{pageTitle}</h1><p>{pageDescription}</p></div>
            <div className="date-range"><span className="live-dot" /> Last 7 days <ChevronDown size={14} /></div>
          </div>
          <Outlet />
          <footer className="page-footer"><span><BadgeCheck size={13} /> AgentOptimize · Measure before you optimize</span><span>v0.4.0</span></footer>
        </div>
      </main>
    </div>
  )
}
