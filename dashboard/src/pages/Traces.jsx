import { useState } from 'react'
import Badge from '../components/Badge'
import DataTable from '../components/DataTable'
import { Loading, ErrorMessage } from '../components/Loading'
import { useApi } from '../hooks/useApi'
import { api } from '../lib/api'

const fmt = (n) => `$${n.toFixed(4)}`
const fmtMs = (n) => (n >= 1000 ? `${(n / 1000).toFixed(1)}s` : `${n.toFixed(0)}ms`)

const columns = [
  { key: 'trace_id', label: 'Trace ID', render: (v) => <span className="font-mono text-xs">{v?.slice(0, 12)}…</span> },
  { key: 'total_cost', label: 'Cost', render: (v) => fmt(v) },
  { key: 'duration_ms', label: 'Duration', render: (v) => fmtMs(v) },
  { key: 'model_call_count', label: 'Models' },
  { key: 'tool_call_count', label: 'Tools' },
  { key: 'retry_count', label: 'Retries' },
  { key: 'success', label: 'Status', render: (v) => <Badge value={v ? 'pass' : 'fail'} /> },
  { key: 'source_framework', label: 'Framework' },
]

export default function Traces() {
  const [selected, setSelected] = useState(null)
  const { data, loading, error } = useApi(() => api.traces({ limit: 100 }), [])
  const { data: detail, loading: detailLoading } = useApi(
    () => (selected ? api.trace(selected) : Promise.resolve(null)),
    [selected],
  )
  const { data: waste } = useApi(
    () => (selected ? api.traceWaste(selected) : Promise.resolve(null)),
    [selected],
  )

  if (loading) return <Loading />
  if (error) return <ErrorMessage message={error} />

  return (
    <div className="space-y-6">
      <div className="pb-2 border-b border-slate-200/70">
        <h1 className="text-2xl font-bold tracking-tight text-slate-900">Traces</h1>
        <p className="text-sm text-slate-500 mt-0.5">
          <span className="font-mono text-emerald-700 font-semibold">{data?.count || 0}</span> traces recorded in warehouse
        </p>
      </div>

      <DataTable
        columns={columns}
        rows={(data?.traces || []).map((t) => ({ ...t, id: t.trace_id }))}
        onRowClick={(row) => setSelected(row.trace_id)}
        emptyMessage="No traces ingested yet. Send traces via OTLP to /v1/traces."
      />

      {/* Trace detail */}
      {selected && detail && !detailLoading && (
        <div className="bg-white/95 rounded-xl border border-slate-200/90 p-6 space-y-5 shadow-xs">
          <div className="flex items-center justify-between pb-3 border-b border-slate-100">
            <div>
              <span className="font-mono text-xs text-slate-400">TRACE INSPECTOR</span>
              <h2 className="text-lg font-semibold font-mono text-slate-900 tracking-tight">{detail.trace_id}</h2>
            </div>
            <button
              onClick={() => setSelected(null)}
              className="text-xs font-mono text-slate-400 hover:text-slate-700 px-2 py-1 rounded bg-slate-100/80 hover:bg-slate-200 transition-colors"
            >
              ✕ Close
            </button>
          </div>

          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
            <div className="bg-slate-50/80 border border-slate-200/60 rounded-lg p-3">
              <p className="text-[11px] font-mono uppercase text-slate-500">Total Cost</p>
              <p className="font-mono font-bold text-slate-900 text-base mt-0.5">{fmt(detail.total_cost)}</p>
            </div>
            <div className="bg-slate-50/80 border border-slate-200/60 rounded-lg p-3">
              <p className="text-[11px] font-mono uppercase text-slate-500">Duration</p>
              <p className="font-mono font-bold text-slate-900 text-base mt-0.5">{fmtMs(detail.duration_ms)}</p>
            </div>
            <div className="bg-slate-50/80 border border-slate-200/60 rounded-lg p-3">
              <p className="text-[11px] font-mono uppercase text-slate-500">Input Tokens</p>
              <p className="font-mono font-bold text-slate-900 text-base mt-0.5">{detail.total_input_tokens?.toLocaleString()}</p>
            </div>
            <div className="bg-slate-50/80 border border-slate-200/60 rounded-lg p-3">
              <p className="text-[11px] font-mono uppercase text-slate-500">Output Tokens</p>
              <p className="font-mono font-bold text-slate-900 text-base mt-0.5">{detail.total_output_tokens?.toLocaleString()}</p>
            </div>
          </div>

          {/* Waste report */}
          {waste && (
            <div className="border-t border-slate-100 pt-4 space-y-3">
              <div className="flex items-center justify-between">
                <h3 className="font-mono text-xs uppercase tracking-wider text-slate-500">
                  Waste Attribution & Efficiency
                </h3>
                <span className="font-mono text-xs font-semibold px-2 py-0.5 rounded bg-emerald-50 text-emerald-800 border border-emerald-200/80">
                  Efficiency: {((waste.efficiency_score || 0) * 100).toFixed(0)}%
                </span>
              </div>
              <div className="grid grid-cols-3 gap-3 text-sm">
                <div className="bg-emerald-50/80 border border-emerald-200/60 rounded-lg p-3">
                  <p className="text-[11px] font-mono uppercase text-emerald-800">Useful Work</p>
                  <p className="font-mono font-bold text-emerald-700 text-base mt-0.5">{fmt(waste.useful_work_cost || 0)}</p>
                </div>
                <div className="bg-rose-50/80 border border-rose-200/60 rounded-lg p-3">
                  <p className="text-[11px] font-mono uppercase text-rose-800">Attributed Waste</p>
                  <p className="font-mono font-bold text-rose-700 text-base mt-0.5">{fmt(waste.total_waste || 0)}</p>
                </div>
                <div className="bg-slate-50/80 border border-slate-200/60 rounded-lg p-3">
                  <p className="text-[11px] font-mono uppercase text-slate-500">Detections</p>
                  <p className="font-mono font-bold text-slate-900 text-base mt-0.5">{waste.detections?.length || 0}</p>
                </div>
              </div>
              {waste.detections?.length > 0 && (
                <div className="space-y-2 pt-1">
                  {waste.detections.map((d) => (
                    <div key={d.detection_id} className="bg-slate-50/70 border border-slate-200/60 rounded-lg p-3 text-sm flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <Badge value={d.category} />
                        <Badge value={d.confidence} />
                        <span className="text-slate-700 text-xs font-medium">{d.title}</span>
                      </div>
                      <span className="font-mono text-xs font-semibold text-rose-600">{fmt(d.estimated_waste_cost)}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Spans */}
          {detail.spans?.length > 0 && (
            <div className="border-t border-slate-100 pt-4 space-y-2">
              <h3 className="font-mono text-xs uppercase tracking-wider text-slate-500">
                Spans ({detail.spans.length})
              </h3>
              <div className="space-y-1.5 max-h-64 overflow-y-auto">
                {detail.spans.map((s) => (
                  <div key={s.span_id} className="flex items-center gap-2.5 text-xs font-mono bg-slate-50/80 border border-slate-200/50 rounded-lg px-3 py-2">
                    <Badge value={s.span_kind} />
                    <span className="text-slate-800 truncate flex-1 font-sans text-xs">{s.name}</span>
                    {s.model_call && <span className="text-sky-700 font-semibold">{s.model_call.model}</span>}
                    {s.tool_call && <span className="text-teal-700 font-semibold">{s.tool_call.tool_name}</span>}
                    <span className="text-slate-400">{fmtMs(s.duration_ms)}</span>
                    <span className="text-slate-700 font-medium">{fmt(s.cost?.total_cost || 0)}</span>
                    <Badge value={s.status} />
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
