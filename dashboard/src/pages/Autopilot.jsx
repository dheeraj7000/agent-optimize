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
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Autopilot</h1>
          <p className="text-gray-500 mt-1">Automated execution policies within your constraints</p>
        </div>
        <Badge value={s.mode} className="text-base px-3 py-1" />
      </div>

      {/* Mode selector */}
      <div className="bg-white rounded-xl border border-gray-200 p-5">
        <h2 className="font-medium text-sm text-gray-700 mb-3">Operating Mode</h2>
        <div className="flex gap-2">
          {modes.map((m) => (
            <button
              key={m}
              onClick={() => changeMode(m)}
              disabled={switching}
              className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                s.mode === m
                  ? 'bg-green-600 text-white'
                  : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
              } disabled:opacity-50`}
            >
              {m}
            </button>
          ))}
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
          label="Est. Savings"
          value={fmt(s.estimated_monthly_savings || 0)}
          color="green"
        />
      </div>

      {/* Component stats */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="bg-white rounded-xl border border-gray-200 p-5">
          <div className="flex items-center gap-2 mb-3">
            <Router size={18} className="text-blue-600" />
            <h3 className="font-medium">Model Router</h3>
          </div>
          <div className="space-y-2 text-sm">
            <div className="flex justify-between"><span className="text-gray-500">Routed</span><span>{router.total_routed || 0}</span></div>
            <div className="flex justify-between"><span className="text-gray-500">Savings</span><span>{fmt(router.total_savings)}</span></div>
            {router.by_complexity && Object.entries(router.by_complexity).map(([k, v]) => (
              <div key={k} className="flex justify-between"><span className="text-gray-400">{k}</span><span>{v}</span></div>
            ))}
          </div>
        </div>

        <div className="bg-white rounded-xl border border-gray-200 p-5">
          <div className="flex items-center gap-2 mb-3">
            <ShieldCheck size={18} className="text-amber-600" />
            <h3 className="font-medium">Adaptive Verification</h3>
          </div>
          <div className="space-y-2 text-sm">
            <div className="flex justify-between"><span className="text-gray-500">Decisions</span><span>{verifier.total_decisions || 0}</span></div>
            <div className="flex justify-between"><span className="text-gray-500">Skip Rate</span><span>{((verifier.skip_rate || 0) * 100).toFixed(0)}%</span></div>
            <div className="flex justify-between"><span className="text-gray-500">Savings</span><span>{fmt(verifier.estimated_savings)}</span></div>
          </div>
        </div>

        <div className="bg-white rounded-xl border border-gray-200 p-5">
          <div className="flex items-center gap-2 mb-3">
            <RotateCcw size={18} className="text-purple-600" />
            <h3 className="font-medium">Recovery Selector</h3>
          </div>
          <div className="space-y-2 text-sm">
            <div className="flex justify-between"><span className="text-gray-500">Decisions</span><span>{recovery.total_decisions || 0}</span></div>
            <div className="flex justify-between"><span className="text-gray-500">Rules</span><span>{recovery.rules_count || 0}</span></div>
            {recovery.by_strategy && Object.entries(recovery.by_strategy).map(([k, v]) => (
              <div key={k} className="flex justify-between"><span className="text-gray-400">{k}</span><span>{v}</span></div>
            ))}
          </div>
        </div>
      </div>

      {/* Recent decisions */}
      <div>
        <h2 className="text-lg font-semibold text-gray-900 mb-3">Recent Decisions</h2>
        <DataTable
          columns={decisionCols}
          rows={(decisions?.decisions || []).map((d) => ({ ...d, id: d.decision_id }))}
          emptyMessage="No autopilot decisions yet."
        />
      </div>
    </div>
  )
}
