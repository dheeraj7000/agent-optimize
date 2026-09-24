import { NavLink, Outlet } from 'react-router-dom'
import {
  LayoutDashboard, AlertTriangle, ListChecks, Activity,
  Bot, Zap, ExternalLink, Terminal, ShieldCheck, BookOpen
} from 'lucide-react'

const nav = [
  { to: '/', icon: LayoutDashboard, label: 'Overview' },
  { to: '/recommendations', icon: ListChecks, label: 'Recommendations' },
  { to: '/traces', icon: Activity, label: 'Traces' },
  { to: '/validation', icon: ShieldCheck, label: 'Validation' },
  { to: '/autopilot', icon: Bot, label: 'Autopilot' },
  { to: '/quickstart', icon: BookOpen, label: 'Quickstart & Docs' },
]

function SidebarLink({ to, icon: Icon, label }) {
  return (
    <NavLink
      to={to}
      end={to === '/'}
      className={({ isActive }) =>
        `group flex items-center justify-between px-3 py-2 rounded-lg text-sm transition-all duration-150 ${
          isActive
            ? 'bg-gradient-to-r from-emerald-500/10 to-sky-500/10 text-emerald-950 font-medium border border-emerald-500/20 shadow-xs'
            : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100/80 font-normal'
        }`
      }
    >
      {({ isActive }) => (
        <>
          <div className="flex items-center gap-2.5">
            <Icon
              size={17}
              className={`transition-colors ${
                isActive ? 'text-emerald-600' : 'text-slate-400 group-hover:text-slate-700'
              }`}
            />
            <span className="tracking-tight">{label}</span>
          </div>
          {isActive && (
            <span className="w-1.5 h-1.5 rounded-full bg-gradient-to-r from-emerald-500 to-sky-500"></span>
          )}
        </>
      )}
    </NavLink>
  )
}

export default function Layout() {
  return (
    <div className="flex h-screen bg-[#f8fafc] text-slate-800 font-sans">
      {/* Sidebar Rail */}
      <aside className="w-64 border-r border-slate-200/80 bg-white/95 backdrop-blur-sm flex flex-col justify-between shrink-0 shadow-[1px_0_4px_rgba(0,0,0,0.02)]">
        <div>
          {/* Brand header */}
          <div className="px-5 py-4 border-b border-slate-200/70">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2.5">
                <div className="w-7 h-7 rounded-lg bg-gradient-to-tr from-emerald-500 via-teal-500 to-sky-500 flex items-center justify-center text-white shadow-xs">
                  <Zap size={15} className="stroke-[2.5]" />
                </div>
                <div className="flex flex-col">
                  <span className="text-[15px] font-semibold tracking-tight text-slate-900 leading-tight">
                    AgentOptimize
                  </span>
                  <span className="text-[11px] font-mono tracking-tight text-slate-400">
                    FinOps Engine
                  </span>
                </div>
              </div>
              <span className="font-mono text-[10px] font-medium text-emerald-800 bg-emerald-50 border border-emerald-200/80 px-1.5 py-0.5 rounded">
                v0.4.0
              </span>
            </div>
          </div>

          {/* Live indicator chip */}
          <div className="px-3.5 pt-3 pb-1">
            <div className="flex items-center justify-between px-2.5 py-1.5 rounded-md bg-slate-50 border border-slate-200/60 text-[11px] font-mono">
              <div className="flex items-center gap-2">
                <span className="relative flex h-2 w-2">
                  <span className="animate-live-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                  <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
                </span>
                <span className="text-slate-600 font-medium">OTLP Receiver</span>
              </div>
              <span className="text-slate-400">:8080</span>
            </div>
          </div>

          {/* Navigation doors */}
          <nav className="px-3 py-3 space-y-1">
            <div className="px-2 pb-1.5 text-[10px] font-mono font-medium uppercase tracking-wider text-slate-400">
              Platform
            </div>
            {nav.map((n) => (
              <SidebarLink key={n.to} {...n} />
            ))}
          </nav>
        </div>

        {/* Sidebar Footer */}
        <div className="p-3 border-t border-slate-200/70 space-y-2">
          <a
            href="/docs"
            target="_blank"
            rel="noreferrer"
            className="flex items-center justify-between px-3 py-2 rounded-lg text-xs font-medium text-slate-600 hover:text-slate-900 hover:bg-slate-100/80 transition-colors"
          >
            <span className="flex items-center gap-2">
              <Terminal size={14} className="text-slate-400" />
              API Documentation
            </span>
            <ExternalLink size={12} className="text-slate-400" />
          </a>
          <div className="px-3 py-1 flex items-center justify-between text-[11px] font-mono text-slate-400">
            <span>status: healthy</span>
            <span className="text-emerald-600 font-medium">● 200 OK</span>
          </div>
        </div>
      </aside>

      {/* Main Content Area */}
      <main className="flex-1 overflow-auto">
        <div className="max-w-7xl mx-auto px-8 py-7">
          <Outlet />
        </div>
      </main>
    </div>
  )
}
