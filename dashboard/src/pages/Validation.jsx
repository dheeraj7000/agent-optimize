import { ShieldCheck } from 'lucide-react'
import Badge from '../components/Badge'
import DataTable from '../components/DataTable'
import StatCard from '../components/StatCard'
import { Loading, ErrorMessage } from '../components/Loading'
import { useApi } from '../hooks/useApi'
import { api } from '../lib/api'

const fmt = (n) => `$${(n || 0).toFixed(2)}`

const proofCols = [
  { key: 'recommendation_id', label: 'Recommendation', render: (v) => <span className="font-mono text-xs">{v?.slice(0, 12)}</span> },
  { key: 'status', label: 'Status', render: (v) => <Badge value={v} /> },
  { key: 'actual_savings_pct', label: 'Savings', render: (v) => `${(v || 0).toFixed(1)}%` },
  { key: 'quality_preserved', label: 'Quality', render: (v) => <Badge value={v ? 'pass' : 'fail'} /> },
  { key: 'eval_verdict', label: 'Eval', render: (v) => <Badge value={v} /> },
  { key: 'confidence', label: 'Confidence', render: (v) => <Badge value={v} /> },
  { key: 'summary', label: 'Summary' },
]

const canaryCols = [
  { key: 'canary_id', label: 'Canary', render: (v) => <span className="font-mono text-xs">{v?.slice(0, 12)}</span> },
  { key: 'status', label: 'Status', render: (v) => <Badge value={v} /> },
  { key: 'traffic_pct', label: 'Traffic', render: (v) => `${v}%` },
  { key: 'checkpoint_count', label: 'Checkpoints' },
  { key: 'final_verdict', label: 'Verdict', render: (v) => <Badge value={v} /> },
]

export default function Validation() {
  const { data: evaluators } = useApi(() => api.evaluators(), [])
  const { data: proofs, loading, error } = useApi(() => api.proofs(), [])
  const { data: canaries } = useApi(() => api.canaries(), [])

  if (loading) return <Loading />
  if (error) return <ErrorMessage message={error} />

  return (
    <div className="space-y-7">
      <div className="pb-2 border-b border-slate-200/70">
        <h1 className="text-2xl font-bold tracking-tight text-slate-900">Validation & Canary</h1>
        <p className="text-sm text-slate-500 mt-0.5">Counterfactual replay proofs, automated quality evaluators, and canary traffic monitors</p>
      </div>

      {/* Evaluators */}
      <div className="space-y-3">
        <div className="flex items-center gap-2">
          <h2 className="text-base font-semibold tracking-tight text-slate-900">Quality Evaluators</h2>
          <span className="font-mono text-xs text-slate-400">({(evaluators?.evaluators || []).length} active)</span>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          {(evaluators?.evaluators || []).map((e) => (
            <div key={e.name} className="bg-white/95 rounded-xl border border-slate-200/80 p-4 shadow-xs hover:border-slate-300 transition-all">
              <div className="flex items-center gap-2.5">
                <div className="p-1.5 rounded-md bg-emerald-50 text-emerald-600 border border-emerald-200/60">
                  <ShieldCheck size={15} />
                </div>
                <span className="font-medium text-sm text-slate-900 tracking-tight">{e.name}</span>
              </div>
              <p className="text-xs text-slate-500 mt-2 leading-relaxed">{e.description}</p>
            </div>
          ))}
        </div>
      </div>

      {/* Proofs */}
      <div className="space-y-3">
        <div className="flex items-center gap-2">
          <h2 className="text-base font-semibold tracking-tight text-slate-900">Savings Proofs</h2>
          <span className="font-mono text-xs text-slate-400">({(proofs?.proofs || []).length})</span>
        </div>
        <DataTable
          columns={proofCols}
          rows={(proofs?.proofs || []).map((p) => ({ ...p, id: p.proof_id }))}
          emptyMessage="No proofs yet. Validate a replay experiment to generate a mathematical proof."
        />
      </div>

      {/* Canaries */}
      <div className="space-y-3">
        <div className="flex items-center gap-2">
          <h2 className="text-base font-semibold tracking-tight text-slate-900">Canary Deployments</h2>
          <span className="font-mono text-xs text-slate-400">({(canaries?.canaries || []).length})</span>
        </div>
        <DataTable
          columns={canaryCols}
          rows={(canaries?.canaries || []).map((c) => ({ ...c, id: c.canary_id }))}
          emptyMessage="No canary deployments active currently."
        />
      </div>
    </div>
  )
}
