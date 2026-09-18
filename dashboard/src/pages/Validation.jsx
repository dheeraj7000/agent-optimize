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
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Validation</h1>
        <p className="text-gray-500 mt-1">Savings proofs, quality evaluators, and canary monitoring</p>
      </div>

      {/* Evaluators */}
      <div>
        <h2 className="text-lg font-semibold text-gray-900 mb-3">Quality Evaluators</h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          {(evaluators?.evaluators || []).map((e) => (
            <div key={e.name} className="bg-white rounded-xl border border-gray-200 p-4">
              <div className="flex items-center gap-2">
                <ShieldCheck size={16} className="text-green-600" />
                <span className="font-medium text-sm">{e.name}</span>
              </div>
              <p className="text-xs text-gray-500 mt-1">{e.description}</p>
            </div>
          ))}
        </div>
      </div>

      {/* Proofs */}
      <div>
        <h2 className="text-lg font-semibold text-gray-900 mb-3">Savings Proofs</h2>
        <DataTable
          columns={proofCols}
          rows={(proofs?.proofs || []).map((p) => ({ ...p, id: p.proof_id }))}
          emptyMessage="No proofs yet. Validate a replay experiment to generate a proof."
        />
      </div>

      {/* Canaries */}
      <div>
        <h2 className="text-lg font-semibold text-gray-900 mb-3">Canary Deployments</h2>
        <DataTable
          columns={canaryCols}
          rows={(canaries?.canaries || []).map((c) => ({ ...c, id: c.canary_id }))}
          emptyMessage="No canary deployments."
        />
      </div>
    </div>
  )
}
