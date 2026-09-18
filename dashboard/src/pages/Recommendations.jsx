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
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Recommendations</h1>
          <p className="text-gray-500 mt-1">Actionable optimizations ranked by business value</p>
        </div>
        <button
          onClick={generate}
          disabled={generating}
          className="flex items-center gap-2 px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:opacity-50 text-sm font-medium"
        >
          <RefreshCw size={16} className={generating ? 'animate-spin' : ''} />
          Generate
        </button>
      </div>

      {/* Summary stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatCard label="Total" value={s.total || 0} icon={ListChecks} color="blue" />
        <StatCard label="Identified Savings" value={fmt(s.total_identified_savings || 0)} color="amber" />
        <StatCard label="Accepted Savings" value={fmt(s.total_accepted_savings || 0)} color="green" />
        <StatCard label="Verified Savings" value={fmt(s.total_verified_savings || 0)} color="green" />
      </div>

      {/* Recommendations table */}
      <DataTable
        columns={columns}
        rows={(recs?.recommendations || []).map((r) => ({ ...r, id: r.recommendation_id }))}
        onRowClick={(row) => setSelected(row.recommendation_id)}
        emptyMessage="No recommendations yet. Click Generate to analyze traces."
      />

      {/* Detail panel */}
      {selected && detail && !detailLoading && (
        <div className="bg-white rounded-xl border border-gray-200 p-6 space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold">{detail.title}</h2>
            <button onClick={() => setSelected(null)} className="text-gray-400 hover:text-gray-600 text-sm">
              Close
            </button>
          </div>
          <p className="text-gray-600 text-sm">{detail.description}</p>

          {/* Impact */}
          {detail.impact && (
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
              <div className="bg-gray-50 rounded-lg p-3">
                <p className="text-gray-500">Monthly Savings</p>
                <p className="font-bold">{fmt(detail.impact.monthly_savings)}</p>
              </div>
              <div className="bg-gray-50 rounded-lg p-3">
                <p className="text-gray-500">Cost Reduction</p>
                <p className="font-bold">{detail.impact.cost_reduction_pct}%</p>
              </div>
              <div className="bg-gray-50 rounded-lg p-3">
                <p className="text-gray-500">Quality Impact</p>
                <p className="font-bold">{(detail.impact.quality_delta * 100).toFixed(2)}%</p>
              </div>
              <div className="bg-gray-50 rounded-lg p-3">
                <p className="text-gray-500">Quality Risk</p>
                <Badge value={detail.impact.quality_risk} />
              </div>
            </div>
          )}

          {/* Action items */}
          {detail.action_items?.length > 0 && (
            <div>
              <h3 className="font-medium text-sm text-gray-700 mb-2">Action Items</h3>
              <ol className="list-decimal list-inside space-y-1 text-sm text-gray-600">
                {detail.action_items.map((item, i) => <li key={i}>{item}</li>)}
              </ol>
            </div>
          )}

          {/* Lifecycle actions */}
          <div className="flex gap-2 pt-2 border-t border-gray-100">
            {detail.status === 'pending' && (
              <>
                <button onClick={() => transition('accept')} className="px-3 py-1.5 bg-blue-600 text-white rounded-lg text-sm">Accept</button>
                <button onClick={() => transition('reject')} className="px-3 py-1.5 bg-red-100 text-red-700 rounded-lg text-sm">Reject</button>
              </>
            )}
            {['accepted', 'validated'].includes(detail.status) && (
              <button onClick={() => transition('deploy')} className="px-3 py-1.5 bg-green-600 text-white rounded-lg text-sm">Deploy</button>
            )}
            {detail.status === 'deployed' && (
              <>
                <button onClick={() => transition('verify')} className="px-3 py-1.5 bg-green-600 text-white rounded-lg text-sm">Verify</button>
                <button onClick={() => transition('rollback')} className="px-3 py-1.5 bg-red-100 text-red-700 rounded-lg text-sm">Rollback</button>
              </>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
