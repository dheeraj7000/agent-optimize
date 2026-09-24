import { useState } from 'react'
import { Bot, Router, ShieldCheck, RotateCcw } from 'lucide-react'
import Badge from '../components/Badge'
import StatCard from '../components/StatCard'
import DataTable from '../components/DataTable'
import { Loading, ErrorMessage } from '../components/Loading'
import { useApi } from '../hooks/useApi'
import { api } from '../lib/api'

const fmt = (n) => `$${(n || 0).toFixed(2)}`

const decisionCols = [
  { key: 'action_type', label: 'Action' },
  { key: 'action_description', label: 'Description' },
  { key: 'outcome', label: 'Outcome', render: (v) => <Badge value={v} /> },
  { key: 'expected_savings', label: 'Savings', render: (v) => fmt(v) },
  { key: 'constraints_satisfied', label: 'Constraints', render: (v) => <Badge value={v ? 'pass' : 'fail'} /> },
  { key: 'applied', label: 'Applied', render: (v) => v ? '✓' : '—' },
]

const modes = ['off', 'suggest', 'supervised', 'autonomous']

export default function Autopilot() {
  const { data: status, loading, error, refetch } = useApi(() => api.autopilotStatus(), [])
  const { data: decisions } = useApi(() => api.decisions(20), [])
  const [switching, setSwitching] = useState(false)

  if (loading) return <Loading />
  if (error) return <ErrorMessage message={error} />

  const s = status || {}
  const st = s.stats || {}
  const router = st.router || {}
  const verifier = st.verifier || {}
  const recovery = st.recovery || {}

  const changeMode = async (mode) => {
    setSwitching(true)
    try {
      await api.setMode(mode)
      refetch()
    } finally {
      setSwitching(false)
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between pb-2 border-b border-slate-200/70">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-900">Autopilot</h1>
          <p className="text-sm text-slate-500 mt-0.5">Automated policy execution engine constrained by SLA, risk, and quality thresholds</p>
        </div>
        <Badge value={s.mode} className="text-xs px-3 py-1 font-semibold" />
      </div>

      {/* Mode selector */}
      <div className="bg-white/95 rounded-xl border border-slate-200/80 p-5 shadow-xs">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div>
            <h2 className="font-mono text-xs uppercase tracking-wider text-slate-500">Operating Policy Mode</h2>
            <p className="text-xs text-slate-400 mt-0.5">Defines agent autonomy level for routing, verification, and recovery</p>
          </div>
          <div className="inline-flex p-1 rounded-lg bg-slate-100/90 border border-slate-200/80 gap-1">
            {modes.map((m) => (
              <button
                key={m}
                onClick={() => changeMode(m)}
                disabled={switching}
                className={`px-3 py-1.5 rounded-md text-xs font-mono font-medium transition-all ${
                  s.mode === m
                    ? 'bg-white text-emerald-950 shadow-xs border border-slate-200/80 font-semibold'
                    : 'text-slate-600 hover:text-slate-900 hover:bg-white/50'
                } disabled:opacity-50`}
              >
                {m}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatCard
          label="Decisions Made"
          value={s.decisions_made || 0}
          icon={Bot}
          color="blue"
        />
        <StatCard
          label="Decisions Applied"
          value={s.decisions_applied || 0}
          icon={Bot}
          color="green"
        />
        <StatCard
          label="Decisions Rejected"
          value={s.decisions_rejected || 0}
          color="red"
        />
        <StatCard
          label="Est. Monthly Savings"
          value={fmt(s.estimated_monthly_savings || 0)}
          color="green"
        />
      </div>

      {/* Component stats */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="bg-white/95 rounded-xl border border-slate-200/80 p-5 shadow-xs">
          <div className="flex items-center gap-2.5 mb-3.5 pb-2.5 border-b border-slate-100">
            <div className="p-1.5 rounded-md bg-sky-50 text-sky-700 border border-sky-200/60">
              <Router size={15} />
            </div>
            <h3 className="font-semibold text-sm text-slate-900 tracking-tight">Model Router</h3>
          </div>
          <div className="space-y-2 text-xs font-mono">
            <div className="flex justify-between py-1 border-b border-slate-50"><span className="text-slate-500">Total Routed</span><span className="font-semibold text-slate-800">{router.total_routed || 0}</span></div>
            <div className="flex justify-between py-1 border-b border-slate-50"><span className="text-slate-500">Savings</span><span className="font-semibold text-emerald-700">{fmt(router.total_savings)}</span></div>
            {router.by_complexity && Object.entries(router.by_complexity).map(([k, v]) => (
              <div key={k} className="flex justify-between py-0.5 text-slate-400"><span>{k}</span><span className="text-slate-700 font-medium">{v}</span></div>
            ))}
          </div>
        </div>

        <div className="bg-white/95 rounded-xl border border-slate-200/80 p-5 shadow-xs">
          <div className="flex items-center gap-2.5 mb-3.5 pb-2.5 border-b border-slate-100">
            <div className="p-1.5 rounded-md bg-emerald-50 text-emerald-700 border border-emerald-200/60">
              <ShieldCheck size={15} />
            </div>
            <h3 className="font-semibold text-sm text-slate-900 tracking-tight">Adaptive Verification</h3>
          </div>
          <div className="space-y-2 text-xs font-mono">
            <div className="flex justify-between py-1 border-b border-slate-50"><span className="text-slate-500">Decisions</span><span className="font-semibold text-slate-800">{verifier.total_decisions || 0}</span></div>
            <div className="flex justify-between py-1 border-b border-slate-50"><span className="text-slate-500">Skip Rate</span><span className="font-semibold text-sky-700">{((verifier.skip_rate || 0) * 100).toFixed(0)}%</span></div>
            <div className="flex justify-between py-1 border-b border-slate-50"><span className="text-slate-500">Savings</span><span className="font-semibold text-emerald-700">{fmt(verifier.estimated_savings)}</span></div>
          </div>
        </div>

        <div className="bg-white/95 rounded-xl border border-slate-200/80 p-5 shadow-xs">
          <div className="flex items-center gap-2.5 mb-3.5 pb-2.5 border-b border-slate-100">
            <div className="p-1.5 rounded-md bg-teal-50 text-teal-700 border border-teal-200/60">
              <RotateCcw size={15} />
            </div>
            <h3 className="font-semibold text-sm text-slate-900 tracking-tight">Recovery Selector</h3>
          </div>
          <div className="space-y-2 text-xs font-mono">
            <div className="flex justify-between py-1 border-b border-slate-50"><span className="text-slate-500">Decisions</span><span className="font-semibold text-slate-800">{recovery.total_decisions || 0}</span></div>
            <div className="flex justify-between py-1 border-b border-slate-50"><span className="text-slate-500">Active Rules</span><span className="font-semibold text-slate-800">{recovery.rules_count || 0}</span></div>
            {recovery.by_strategy && Object.entries(recovery.by_strategy).map(([k, v]) => (
              <div key={k} className="flex justify-between py-0.5 text-slate-400"><span>{k}</span><span className="text-slate-700 font-medium">{v}</span></div>
            ))}
          </div>
        </div>
      </div>

      {/* Recent decisions */}
      <div className="space-y-3">
        <div className="flex items-center gap-2">
          <h2 className="text-base font-semibold tracking-tight text-slate-900">Recent Decisions</h2>
          <span className="font-mono text-xs text-slate-400">({(decisions?.decisions || []).length})</span>
        </div>
        <DataTable
          columns={decisionCols}
          rows={(decisions?.decisions || []).map((d) => ({ ...d, id: d.decision_id }))}
          emptyMessage="No autopilot decisions yet."
        />
      </div>
    </div>
  )
}
