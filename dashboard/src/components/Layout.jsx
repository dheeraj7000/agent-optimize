import { NavLink, Outlet } from 'react-router-dom'
import {
  LayoutDashboard, AlertTriangle, ListChecks, Activity,
  Bot, Settings, Zap,
} from 'lucide-react'

const nav = [
  { to: '/', icon: LayoutDashboard, label: 'Overview' },
  { to: '/recommendations', icon: ListChecks, label: 'Recommendations' },
  { to: '/traces', icon: Activity, label: 'Traces' },
  { to: '/validation', icon: AlertTriangle, label: 'Validation' },
  { to: '/autopilot', icon: Bot, label: 'Autopilot' },
]

function SidebarLink({ to, icon: Icon, label }) {
  return (
    <NavLink
      to={to}
      end={to === '/'}
      className={({ isActive }) =>
        `flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
          isActive
            ? 'bg-green-50 text-green-700'
            : 'text-gray-600 hover:bg-gray-100 hover:text-gray-900'
        }`
      }
    >
      <Icon size={18} />
      {label}
    </NavLink>
  )
}

export default function Layout() {
  return (
    <div className="flex h-screen">
      {/* Sidebar */}
      <aside className="w-60 border-r border-gray-200 bg-white flex flex-col">
        <div className="px-4 py-5 border-b border-gray-200">
          <div className="flex items-center gap-2">
            <Zap size={22} className="text-green-600" />
            <span className="text-lg font-bold text-gray-900">AgentOptimize</span>
          </div>
          <p className="text-xs text-gray-500 mt-1">Observe · Diagnose · Optimize · Prove</p>
        </div>
        <nav className="flex-1 px-3 py-4 space-y-1">
          {nav.map((n) => (
            <SidebarLink key={n.to} {...n} />
          ))}
        </nav>
        <div className="px-4 py-3 border-t border-gray-200 text-xs text-gray-400">
          v0.4.0
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 overflow-auto">
        <div className="max-w-7xl mx-auto px-6 py-6">
          <Outlet />
        </div>
      </main>
    </div>
  )
}
