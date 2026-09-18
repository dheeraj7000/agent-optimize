import { DollarSign, TrendingDown, Target, Percent, Activity, RotateCcw } from 'lucide-react'
import StatCard from '../components/StatCard'
import Badge from '../components/Badge'
import DataTable from '../components/DataTable'
import { Loading, ErrorMessage } from '../components/Loading'
import { useApi } from '../hooks/useApi'
import { api } from '../lib/api'

const fmt = (n) => (n >= 1000 ? `$${(n / 1000).toFixed(1)}k` : `$${n.toFixed(2)}`)
const fmtPct = (n) => `${n.toFixed(1)}%`

const opportunityCols = [
  { key: 'title', label: 'Opportunity' },
  { key: 'category', label: 'Category', render: (v) => <Badge value={v} /> },
  { key: 'confidence', label: 'Confidence', render: (v) => <Badge value={v} /> },
  { key: 'estimated_monthly_waste', label: 'Monthly Waste', render: (v) => fmt(v) },
  { key: 'estimated_annual_savings', label: 'Annual Savings', render: (v) => fmt(v) },
  { key: 'affected_traces_pct', label: 'Affected', render: (v) => fmtPct(v) },
]

export default function Overview() {
  const { data, loading, error } = useApi(() => api.opportunities(7), [])
  const stats = useApi(() => api.stats(), [])

  if (loading) return <Loading />
  if (error) return <ErrorMessage message={error} />

  const d = data || {}
  const s = stats.data || {}

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Opportunity Dashboard</h1>
        <p className="text-gray-500 mt-1">Economic opportunity overview for your AI agent fleet</p>
      </div>

      {/* Headline metrics */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-4">
        <StatCard
          label="AI Spend / Month"
          value={fmt(d.total_ai_spend_monthly || 0)}
          icon={DollarSign}
          color="blue"
        />
        <StatCard
          label="Identified Waste"
          value={fmt(d.identified_waste_monthly || 0)}
          icon={TrendingDown}
          color="red"
        />
        <StatCard
          label="Optimization Potential"
          value={fmtPct(d.optimization_potential_pct || 0)}
          icon={Percent}
          color="amber"
        />
        <StatCard
          label="Optimized Spend"
          value={fmt(d.potential_optimized_spend || 0)}
          icon={Target}
          color="green"
        />
        <StatCard
          label="Est. Annual Savings"
          value={fmt(d.estimated_annual_savings || 0)}
          sub={`${d.traces_analyzed || 0} traces analyzed`}
          icon={DollarSign}
          color="green"
        />
      </div>

      {/* Volume stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatCard label="Traces" value={(s.traces || 0).toLocaleString()} icon={Activity} color="gray" />
        <StatCard label="Model Calls" value={(s.model_calls || 0).toLocaleString()} color="gray" />
        <StatCard label="Tool Calls" value={(s.tool_calls || 0).toLocaleString()} color="gray" />
        <StatCard label="Retries" value={(s.retries || 0).toLocaleString()} icon={RotateCcw} color="amber" />
      </div>

      {/* Top opportunities */}
      <div>
        <h2 className="text-lg font-semibold text-gray-900 mb-3">Top Opportunities</h2>
        <DataTable
          columns={opportunityCols}
          rows={d.opportunities || []}
          emptyMessage="No opportunities detected yet. Ingest traces to start analysis."
        />
      </div>
    </div>
  )
}
