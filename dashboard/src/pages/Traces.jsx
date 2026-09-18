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
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Traces</h1>
        <p className="text-gray-500 mt-1">{data?.count || 0} traces in warehouse</p>
      </div>

      <DataTable
        columns={columns}
        rows={(data?.traces || []).map((t) => ({ ...t, id: t.trace_id }))}
        onRowClick={(row) => setSelected(row.trace_id)}
        emptyMessage="No traces ingested yet. Send traces via OTLP to /v1/traces."
      />

      {/* Trace detail */}
      {selected && detail && !detailLoading && (
        <div className="bg-white rounded-xl border border-gray-200 p-6 space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold font-mono">{detail.trace_id}</h2>
            <button onClick={() => setSelected(null)} className="text-gray-400 hover:text-gray-600 text-sm">Close</button>
          </div>

          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
            <div className="bg-gray-50 rounded-lg p-3">
              <p className="text-gray-500">Total Cost</p>
              <p className="font-bold">{fmt(detail.total_cost)}</p>
            </div>
            <div className="bg-gray-50 rounded-lg p-3">
              <p className="text-gray-500">Duration</p>
              <p className="font-bold">{fmtMs(detail.duration_ms)}</p>
            </div>
            <div className="bg-gray-50 rounded-lg p-3">
              <p className="text-gray-500">Input Tokens</p>
              <p className="font-bold">{detail.total_input_tokens?.toLocaleString()}</p>
            </div>
            <div className="bg-gray-50 rounded-lg p-3">
              <p className="text-gray-500">Output Tokens</p>
              <p className="font-bold">{detail.total_output_tokens?.toLocaleString()}</p>
            </div>
          </div>

          {/* Waste report */}
          {waste && (
            <div className="border-t border-gray-100 pt-4">
              <h3 className="font-medium text-sm text-gray-700 mb-2">
                Waste Analysis — Efficiency: {((waste.efficiency_score || 0) * 100).toFixed(0)}%
              </h3>
              <div className="grid grid-cols-3 gap-3 text-sm">
                <div className="bg-green-50 rounded-lg p-3">
                  <p className="text-gray-500">Useful Work</p>
                  <p className="font-bold text-green-700">{fmt(waste.useful_work_cost || 0)}</p>
                </div>
                <div className="bg-red-50 rounded-lg p-3">
                  <p className="text-gray-500">Estimated Waste</p>
                  <p className="font-bold text-red-700">{fmt(waste.total_waste || 0)}</p>
                </div>
                <div className="bg-gray-50 rounded-lg p-3">
                  <p className="text-gray-500">Detections</p>
                  <p className="font-bold">{waste.detections?.length || 0}</p>
                </div>
              </div>
              {waste.detections?.length > 0 && (
                <div className="mt-3 space-y-2">
                  {waste.detections.map((d) => (
                    <div key={d.detection_id} className="bg-gray-50 rounded-lg p-3 text-sm">
                      <div className="flex items-center gap-2">
                        <Badge value={d.category} />
                        <Badge value={d.confidence} />
                        <span className="text-gray-600">{d.title}</span>
                        <span className="ml-auto font-medium text-red-600">{fmt(d.estimated_waste_cost)}</span>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Spans */}
          {detail.spans?.length > 0 && (
            <div className="border-t border-gray-100 pt-4">
              <h3 className="font-medium text-sm text-gray-700 mb-2">Spans ({detail.spans.length})</h3>
              <div className="space-y-1 max-h-64 overflow-y-auto">
                {detail.spans.map((s) => (
                  <div key={s.span_id} className="flex items-center gap-3 text-xs font-mono bg-gray-50 rounded px-3 py-2">
                    <Badge value={s.span_kind} />
                    <span className="text-gray-700 truncate flex-1">{s.name}</span>
                    {s.model_call && <span className="text-blue-600">{s.model_call.model}</span>}
                    {s.tool_call && <span className="text-purple-600">{s.tool_call.tool_name}</span>}
                    <span className="text-gray-500">{fmtMs(s.duration_ms)}</span>
                    <span className="text-gray-700">{fmt(s.cost?.total_cost || 0)}</span>
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
