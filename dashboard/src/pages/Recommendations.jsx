import { useState } from 'react'
import { ListChecks, RefreshCw } from 'lucide-react'
import Badge from '../components/Badge'
import DataTable from '../components/DataTable'
import StatCard from '../components/StatCard'
import { Loading, ErrorMessage } from '../components/Loading'
import { useApi } from '../hooks/useApi'
import { api } from '../lib/api'

const fmt = (n) => (n >= 1000 ? `$${(n / 1000).toFixed(1)}k` : `$${n.toFixed(2)}`)

const columns = [
  { key: 'title', label: 'Recommendation' },
  { key: 'category', label: 'Category', render: (v) => <Badge value={v} /> },
  { key: 'status', label: 'Status', render: (v) => <Badge value={v} /> },
  { key: 'priority', label: 'Priority', render: (v) => <Badge value={v} /> },
  { key: 'monthly_savings', label: 'Monthly Savings', render: (v) => fmt(v) },
  { key: 'confidence', label: 'Confidence', render: (v) => <Badge value={v} /> },
  { key: 'business_value_score', label: 'Score', render: (v) => v?.toFixed(0) },
]

export default function Recommendations() {
  const [selected, setSelected] = useState(null)
  const { data: recs, loading, error, refetch } = useApi(() => api.recommendations(), [])
  const { data: stats } = useApi(() => api.recommendationStats(), [])
  const { data: detail, loading: detailLoading } = useApi(
    () => (selected ? api.recommendation(selected) : Promise.resolve(null)),
    [selected],
  )

  const [generating, setGenerating] = useState(false)

  const generate = async () => {
    setGenerating(true)
    try {
      await api.generateRecommendations()
      refetch()
    } finally {
      setGenerating(false)
    }
  }

  const transition = async (action) => {
    if (!selected) return
    await api.transitionRecommendation(selected, action)
    refetch()
    setSelected(selected) // re-fetch detail
  }

  if (loading) return <Loading />
  if (error) return <ErrorMessage message={error} />

  const s = stats || {}

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between pb-2 border-b border-slate-200/70">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-900">Recommendations</h1>
          <p className="text-sm text-slate-500 mt-0.5">Counterfactual optimizations ranked by business value</p>
        </div>
        <button
          onClick={generate}
          disabled={generating}
          className="flex items-center gap-2 px-4 py-2 bg-gradient-to-r from-emerald-600 via-teal-600 to-sky-600 text-white rounded-lg hover:from-emerald-700 hover:to-sky-700 disabled:opacity-50 text-sm font-medium transition-all shadow-xs active:scale-[0.98]"
        >
          <RefreshCw size={15} className={generating ? 'animate-spin' : ''} />
          {generating ? 'Analyzing traces…' : 'Generate Recommendations'}
        </button>
      </div>

      {/* Summary stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatCard label="Total Policies" value={s.total || 0} icon={ListChecks} color="blue" />
        <StatCard label="Identified Savings" value={fmt(s.total_identified_savings || 0)} color="cyan" />
        <StatCard label="Accepted Savings" value={fmt(s.total_accepted_savings || 0)} color="green" />
        <StatCard label="Verified In Prod" value={fmt(s.total_verified_savings || 0)} color="green" />
      </div>

      {/* Recommendations table */}
      <DataTable
        columns={columns}
        rows={(recs?.recommendations || []).map((r) => ({ ...r, id: r.recommendation_id }))}
        onRowClick={(row) => setSelected(row.recommendation_id)}
        emptyMessage="No recommendations yet. Click 'Generate Recommendations' to analyze traces."
      />

      {/* Detail panel */}
      {selected && detail && !detailLoading && (
        <div className="bg-white/95 rounded-xl border border-slate-200/90 p-6 space-y-5 shadow-xs">
          <div className="flex items-center justify-between pb-3 border-b border-slate-100">
            <div>
              <span className="font-mono text-xs text-slate-400">REC #{detail.recommendation_id?.slice(0, 8)}</span>
              <h2 className="text-lg font-semibold text-slate-900 tracking-tight">{detail.title}</h2>
            </div>
            <button
              onClick={() => setSelected(null)}
              className="text-xs font-mono text-slate-400 hover:text-slate-700 px-2 py-1 rounded bg-slate-100/80 hover:bg-slate-200 transition-colors"
            >
              ✕ Close
            </button>
          </div>
          <p className="text-slate-600 text-sm leading-relaxed">{detail.description}</p>

          {/* Impact */}
          {detail.impact && (
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
              <div className="bg-slate-50/80 border border-slate-200/60 rounded-lg p-3">
                <p className="text-[11px] font-mono uppercase text-slate-500">Monthly Savings</p>
                <p className="font-mono font-bold text-emerald-700 text-base mt-0.5">{fmt(detail.impact.monthly_savings)}</p>
              </div>
              <div className="bg-slate-50/80 border border-slate-200/60 rounded-lg p-3">
                <p className="text-[11px] font-mono uppercase text-slate-500">Cost Reduction</p>
                <p className="font-mono font-bold text-slate-900 text-base mt-0.5">{detail.impact.cost_reduction_pct}%</p>
              </div>
              <div className="bg-slate-50/80 border border-slate-200/60 rounded-lg p-3">
                <p className="text-[11px] font-mono uppercase text-slate-500">Quality Impact</p>
                <p className="font-mono font-bold text-slate-900 text-base mt-0.5">{(detail.impact.quality_delta * 100).toFixed(2)}%</p>
              </div>
              <div className="bg-slate-50/80 border border-slate-200/60 rounded-lg p-3">
                <p className="text-[11px] font-mono uppercase text-slate-500 mb-1">Quality Risk</p>
                <Badge value={detail.impact.quality_risk} />
              </div>
            </div>
          )}

          {/* Action items */}
          {detail.action_items?.length > 0 && (
            <div className="bg-slate-50/60 border border-slate-200/60 rounded-lg p-4">
              <h3 className="font-mono text-xs uppercase tracking-wider text-slate-500 mb-2">Prescribed Action Items</h3>
              <ol className="list-decimal list-inside space-y-1.5 text-sm text-slate-700">
                {detail.action_items.map((item, i) => <li key={i}>{item}</li>)}
              </ol>
            </div>
          )}

          {/* Lifecycle actions */}
          <div className="flex gap-2 pt-3 border-t border-slate-100">
            {detail.status === 'pending' && (
              <>
                <button
                  onClick={() => transition('accept')}
                  className="px-3.5 py-1.5 bg-sky-600 hover:bg-sky-700 text-white rounded-lg text-xs font-mono font-medium shadow-xs transition-colors"
                >
                  Accept Policy
                </button>
                <button
                  onClick={() => transition('reject')}
                  className="px-3.5 py-1.5 bg-rose-50 hover:bg-rose-100 text-rose-700 border border-rose-200/80 rounded-lg text-xs font-mono font-medium transition-colors"
                >
                  Reject
                </button>
              </>
            )}
            {['accepted', 'validated'].includes(detail.status) && (
              <button
                onClick={() => transition('deploy')}
                className="px-3.5 py-1.5 bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-700 hover:to-teal-700 text-white rounded-lg text-xs font-mono font-medium shadow-xs transition-all"
              >
                Deploy Configuration
              </button>
            )}
            {detail.status === 'deployed' && (
              <>
                <button
                  onClick={() => transition('verify')}
                  className="px-3.5 py-1.5 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg text-xs font-mono font-medium shadow-xs transition-colors"
                >
                  Verify Savings
                </button>
                <button
                  onClick={() => transition('rollback')}
                  className="px-3.5 py-1.5 bg-rose-50 hover:bg-rose-100 text-rose-700 border border-rose-200/80 rounded-lg text-xs font-mono font-medium transition-colors"
                >
                  Rollback
                </button>
              </>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
