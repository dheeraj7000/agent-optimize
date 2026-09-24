import { ArrowDownRight, ArrowUpRight, Activity, CircleDollarSign, Clock3, Layers3, RotateCcw, ShieldCheck, Sparkles, Target, TrendingDown } from 'lucide-react'
import StatCard from '../components/StatCard'
import Badge from '../components/Badge'
import DataTable from '../components/DataTable'
import { Loading, ErrorMessage } from '../components/Loading'
import { useApi } from '../hooks/useApi'
import { api } from '../lib/api'

const money = (value = 0) => {
  const amount = Number(value) || 0
  return new Intl.NumberFormat('en-US', {
    style: 'currency', currency: 'USD', maximumFractionDigits: amount < 100 ? 2 : 0,
    notation: amount >= 10000 ? 'compact' : 'standard', compactDisplay: 'short',
  }).format(amount)
}
const percentage = (value = 0) => `${(Number(value) || 0).toFixed(1)}%`
const number = (value = 0) => (Number(value) || 0).toLocaleString()

const opportunityColumns = [
  {
    key: 'title', label: 'Opportunity', render: (value, row) => <div className="opportunity-cell">
      <strong>{value}</strong><span>{row.description || row.recommendation || 'Evidence-backed optimization opportunity'}</span>
    </div>,
  },
  { key: 'category', label: 'Leak type', render: (value) => <Badge value={value} /> },
  { key: 'confidence', label: 'Confidence', render: (value) => <Badge value={value} /> },
  { key: 'estimated_monthly_waste', label: 'Monthly opportunity', render: (value) => <strong className="table-money">{money(value)}</strong> },
  { key: 'affected_traces_pct', label: 'Traces affected', render: (value) => percentage(value) },
]

export default function Overview() {
  const { data, loading, error } = useApi(() => api.opportunities(7), [])
  const stats = useApi(() => api.stats(168), [])

  if (loading) return <Loading />
  if (error) return <ErrorMessage message={error} />

  const opportunity = data || {}
  const volume = stats.data || {}
  const opportunityRows = opportunity.opportunities || []
  const annualSavings = Number(opportunity.estimated_annual_savings) || 0
  const waste = Number(opportunity.identified_waste_monthly) || 0
  const spend = Number(opportunity.total_ai_spend_monthly) || 0
  const optimizedSpend = Number(opportunity.potential_optimized_spend) || 0

  return (
    <div className="overview-page">
      <section className="overview-hero" aria-label="Estimated annual savings">
        <div>
          <div className="hero-label"><Sparkles size={14} /> Identified optimization potential</div>
          <div className="hero-value">{money(annualSavings)}<span className="hero-period"> / yr</span></div>
          <p className="hero-note">Projection from observed traces — validate before production rollout.</p>
        </div>
        <div className="hero-side">
          <div><span className="hero-side-label">Estimated waste / month</span><div className="hero-side-value">{money(waste)}</div></div>
          <div className="hero-rule" />
          <div className="hero-caption">Based on {number(opportunity.traces_analyzed)} traces in the selected window</div>
        </div>
      </section>

      <section aria-label="Spend overview">
        <div className="section-kicker"><CircleDollarSign size={14} /> COST INTELLIGENCE <span className="section-window">· 7 day analysis</span></div>
        <div className="metrics-grid metrics-grid-primary">
          <StatCard label="AI spend / month" value={money(spend)} icon={CircleDollarSign} color="blue" />
          <StatCard label="Identified waste" value={money(waste)} icon={TrendingDown} color="amber" featured />
          <StatCard label="Optimization potential" value={percentage(opportunity.optimization_potential_pct)} icon={Target} color="green" />
          <StatCard label="Projected optimized spend" value={money(optimizedSpend)} icon={ArrowDownRight} color="gray" />
        </div>
      </section>

      <section aria-label="Agent workload">
        <div className="section-kicker"><Activity size={14} /> WORKLOAD SIGNALS <span className="section-window">· last 7 days</span></div>
        <div className="metric-inline">
          <div className="metric-inline-item"><Activity size={14} /><span>Traces</span><strong>{number(volume.traces)}</strong></div>
          <div className="metric-inline-item"><Layers3 size={14} /><span>Model calls</span><strong>{number(volume.model_calls)}</strong></div>
          <div className="metric-inline-item"><ArrowUpRight size={14} /><span>Tool calls</span><strong>{number(volume.tool_calls)}</strong></div>
          <div className="metric-inline-item"><RotateCcw size={14} /><span>Retries</span><strong>{number(volume.retries)}</strong></div>
          <div className="metric-inline-item"><Clock3 size={14} /><span>Avg. latency</span><strong>{number(Math.round(volume.avg_duration_ms || 0))} ms</strong></div>
          <div className="metric-inline-item"><ShieldCheck size={14} /><span>Success rate</span><strong>{percentage((Number(volume.success_rate) || 0) * 100)}</strong></div>
        </div>
      </section>

      <section className="content-panel" aria-label="Top optimization opportunities">
        <div className="panel-heading">
          <div><h2>Where cost is leaking</h2><p>Ranked signals from trace analysis, with estimated impact and confidence.</p></div>
          <span className="panel-meta">{opportunityRows.length} {opportunityRows.length === 1 ? 'signal' : 'signals'}</span>
        </div>
        <DataTable
          columns={opportunityColumns}
          rows={opportunityRows}
          emptyMessage="Connect an OpenTelemetry source and send agent traces to surface cost and efficiency opportunities."
        />
      </section>
    </div>
  )
}
