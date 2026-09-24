import { useState } from 'react'
import { Link } from 'react-router-dom'
import { DollarSign, TrendingDown, Target, Percent, Activity, RotateCcw, Sparkles, BookOpen } from 'lucide-react'
import StatCard from '../components/StatCard'
import Badge from '../components/Badge'
import DataTable from '../components/DataTable'
import { Loading, ErrorMessage } from '../components/Loading'
import { useApi } from '../hooks/useApi'
import { api } from '../lib/api'

const fmt = (n) => (n >= 1000 ? `$${(n / 1000).toFixed(1)}k` : `$${(n || 0).toFixed(2)}`)
const fmtPct = (n) => `${(n || 0).toFixed(1)}%`

const opportunityCols = [
  {
    key: 'title',
    label: 'Opportunity',
    render: (v, r) => (
      <div>
        <div className="font-medium text-slate-900">{v}</div>
        <div className="text-xs text-slate-400 mt-0.5 line-clamp-1">{r.description}</div>
      </div>
    ),
  },
  { key: 'category', label: 'Category', render: (v) => <Badge value={v} /> },
  { key: 'confidence', label: 'Confidence', render: (v) => <Badge value={v} /> },
  { key: 'estimated_monthly_waste', label: 'Monthly Waste', render: (v) => <span className="font-mono font-medium text-rose-600">{fmt(v)}</span> },
  { key: 'estimated_annual_savings', label: 'Annual Savings', render: (v) => <span className="font-mono font-semibold text-emerald-600">{fmt(v)}</span> },
  { key: 'affected_traces_pct', label: 'Affected', render: (v) => <span className="font-mono text-slate-500">{fmtPct(v)}</span> },
]

export default function Overview() {
  const { data, loading, error, refetch } = useApi(() => api.opportunities(7), [])
  const stats = useApi(() => api.stats(), [])
  const [seeding, setSeeding] = useState(false)

  const handleSeedDemo = async () => {
    setSeeding(true)
    try {
      await fetch('/api/onboarding/seed-demo', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ count: 20 }),
      })
      refetch()
      stats.refetch()
    } finally {
      setSeeding(false)
    }
  }

  if (loading) return <Loading />
  if (error) return <ErrorMessage message={error} />

  const d = data || {}
  const s = stats.data || {}

  return (
    <div className="space-y-7">
      {/* Top Statement Header */}
      <div className="flex flex-col md:flex-row md:items-end justify-between gap-4 pb-2 border-b border-slate-200/70">
        <div>
          <div className="inline-flex items-center gap-2 px-2.5 py-1 rounded-full bg-gradient-to-r from-emerald-50 to-sky-50 border border-emerald-200/80 text-[11px] font-mono text-emerald-900 mb-2">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-live-ping"></span>
            <span>Real-time Ingestion & Waste Attribution</span>
          </div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-900">
            Opportunity Dashboard
          </h1>
          <p className="text-sm text-slate-500 mt-0.5">
            Cost telemetry, waste detection, and savings potential across active agent traces
          </p>
        </div>

        <div className="flex items-center gap-2">
          <Link
            to="/quickstart"
            className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-mono font-medium rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white transition-all shadow-xs"
          >
            <BookOpen size={13} />
            Setup Guide
          </Link>
          <button
            onClick={handleSeedDemo}
            disabled={seeding}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-mono font-medium rounded-lg bg-white border border-slate-200 text-slate-700 hover:bg-slate-50 hover:border-slate-300 disabled:opacity-50 transition-all shadow-2xs"
          >
            <Sparkles size={13} className="text-emerald-500" />
            {seeding ? 'Seeding traces…' : 'Seed demo data'}
          </button>
        </div>
      </div>

      {/* Headline metrics */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
        <StatCard
          label="AI Spend / Mo"
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
          color="cyan"
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
        <StatCard label="Traces Analyzed" value={(s.traces || 0).toLocaleString()} icon={Activity} color="gray" />
        <StatCard label="Model Invocations" value={(s.model_calls || 0).toLocaleString()} color="gray" />
        <StatCard label="Tool Invocations" value={(s.tool_calls || 0).toLocaleString()} color="gray" />
        <StatCard label="Retry Sequence Waste" value={(s.retries || 0).toLocaleString()} icon={RotateCcw} color="amber" />
      </div>

      {/* Top opportunities */}
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <h2 className="text-base font-semibold tracking-tight text-slate-900">
              Ranked Opportunities
            </h2>
            <span className="font-mono text-xs text-slate-400">
              ({(d.opportunities || []).length})
            </span>
          </div>
        </div>

        <DataTable
          columns={opportunityCols}
          rows={d.opportunities || []}
          emptyMessage="No opportunities detected yet. Ingest traces or click 'Seed demo data' to analyze."
        />
      </div>
    </div>
  )
}
