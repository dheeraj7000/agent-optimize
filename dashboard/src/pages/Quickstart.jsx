import { useState } from 'react'
import {
  Terminal, CheckCircle2, Circle, ArrowRight, Copy, Check,
  Send, Sparkles, Code2, BookOpen, Layers, ShieldCheck, Zap
} from 'lucide-react'
import { useApi } from '../hooks/useApi'
import { api } from '../lib/api'
import { Loading } from '../components/Loading'

export default function Quickstart() {
  const { data: onboarding, refetch: refetchOnboarding } = useApi(() => api.onboardingStatus(), [])
  const [activeTab, setActiveTab] = useState('python')
  const [copiedSection, setCopiedSection] = useState(null)
  const [testTraceState, setTestTraceState] = useState({ loading: false, result: null, error: null })
  const [seeding, setSeeding] = useState(false)

  const origin = typeof window !== 'undefined' ? window.location.origin : 'http://localhost:8080'
  const otlpEndpoint = `${origin}/v1/traces`

  const copyToClipboard = (text, key) => {
    navigator.clipboard.writeText(text)
    setCopiedSection(key)
    setTimeout(() => setCopiedSection(null), 2000)
  }

  const handleSendTestTrace = async () => {
    setTestTraceState({ loading: true, result: null, error: null })
    const traceId = 'live-' + Math.random().toString(16).substring(2, 10) + Math.random().toString(16).substring(2, 10)
    const spanId = Math.random().toString(16).substring(2, 10)
    const nowNano = Date.now() * 1000000

    const testPayload = {
      resourceSpans: [{
        resource: {
          attributes: [
            { key: 'service.name', value: { stringValue: 'agent-quickstart-test' } },
            { key: 'telemetry.sdk.language', value: { stringValue: 'python' } }
          ]
        },
        scopeSpans: [{
          scope: { name: 'agent-optimize.tracer' },
          spans: [{
            traceId: traceId,
            spanId: spanId,
            name: 'agent.workflow.chat',
            startTimeUnixNano: String(nowNano - 1200000000),
            endTimeUnixNano: String(nowNano),
            status: { code: 1 },
            attributes: [
              { key: 'gen_ai.system', value: { stringValue: 'openai' } },
              { key: 'gen_ai.request.model', value: { stringValue: 'gpt-4o' } },
              { key: 'gen_ai.usage.input_tokens', value: { intValue: 1450 } },
              { key: 'gen_ai.usage.output_tokens', value: { intValue: 280 } },
            ]
          }]
        }]
      }]
    }

    try {
      const res = await api.sendTrace(testPayload)
      setTestTraceState({ loading: false, result: { traceId, ...res }, error: null })
      await api.completeStep('connect_traces')
      refetchOnboarding()
    } catch (err) {
      setTestTraceState({ loading: false, result: null, error: err.message })
    }
  }

  const handleSeedDemo = async () => {
    setSeeding(true)
    try {
      await api.seedDemo(20)
      await api.completeStep('connect_traces')
      await api.completeStep('view_dashboard')
      refetchOnboarding()
    } finally {
      setSeeding(false)
    }
  }

  const snippets = {
    python: `# 1. Install OpenTelemetry SDK
pip install opentelemetry-api opentelemetry-sdk opentelemetry-exporter-otlp-proto-http

# 2. Configure Exporter in your agent code
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

provider = TracerProvider()
exporter = OTLPSpanExporter(
    endpoint="${otlpEndpoint}",
    # If API authentication is enabled:
    # headers={"Authorization": "Bearer YOUR_API_KEY"}
)
provider.add_span_processor(BatchSpanProcessor(exporter))`,

    langchain: `# LangChain / LangGraph OpenTelemetry Tracing
# Set the standard OTel environment variables:
export OTEL_EXPORTER_OTLP_ENDPOINT="${origin}"
export OTEL_EXPORTER_OTLP_PROTOCOL="http/protobuf"
export OTEL_SERVICE_NAME="customer-support-agent"

# Python agent initialization:
from langchain_core.tracers import LangChainTracer
# Traces are exported to AgentOptimize via the standard OTel collector or SDK`,

    crewai: `# CrewAI OpenTelemetry Integration
import os
os.environ["OTEL_EXPORTER_OTLP_ENDPOINT"] = "${otlpEndpoint}"
os.environ["OTEL_SERVICE_NAME"] = "research-crew"

from crewai import Agent, Crew, Task
# CrewAI spans with model tokens and tool durations are automatically normalized`,

    curl: `curl -X POST ${otlpEndpoint} \\
  -H "Content-Type: application/json" \\
  -d '{
    "resourceSpans": [{
      "resource": {
        "attributes": [{"key": "service.name", "value": {"stringValue": "pilot-agent"}}]
      },
      "scopeSpans": [{
        "scope": {},
        "spans": [{
          "traceId": "testtrace001",
          "spanId": "span001",
          "name": "agent.call",
          "startTimeUnixNano": "1700000000000000000",
          "endTimeUnixNano": "1700000001000000000",
          "status": {"code": 1},
          "attributes": [
            {"key": "gen_ai.system", "value": {"stringValue": "openai"}},
            {"key": "gen_ai.request.model", "value": {"stringValue": "gpt-4o"}},
            {"key": "gen_ai.usage.input_tokens", "value": {"intValue": 800}},
            {"key": "gen_ai.usage.output_tokens", "value": {"intValue": 150}}
          ]
        }]
      }]
    }]
  }'`,

    docker: `# Run production container with persistent storage
docker run -d \\
  --name agentoptimize \\
  -p 8080:8080 \\
  -v /var/data/agentoptimize:/data \\
  -e AGENTOPTIMIZE_DB_PATH=/data/agentoptimize.db \\
  -e AGENTOPTIMIZE_API_KEY_REQUIRED=true \\
  agentoptimize

# Generate customer API key:
agent-optimize create-key --tenant customer-acme --name "Production Trace Ingestion"`,
  }

  const steps = onboarding?.steps || [
    { key: 'connect_traces', title: 'Connect Agent Traces', description: 'Send your first OTel traces to /v1/traces', completed: false },
    { key: 'view_dashboard', title: 'View Opportunity Dashboard', description: 'Analyze monthly AI spend and identified waste', completed: false },
    { key: 'generate_recommendations', title: 'Generate Recommendations', description: 'Run counterfactual waste detection algorithms', completed: false },
    { key: 'review_recommendation', title: 'Review Recommendation Details', description: 'Inspect impact projections, confidence, and action items', completed: false },
    { key: 'run_replay', title: 'Run Replay Experiment', description: 'Validate optimizations against quality evaluators', completed: false },
    { key: 'configure_autopilot', title: 'Configure Autopilot Policy', description: 'Enable autonomous or supervised model routing', completed: false },
  ]

  const completedCount = onboarding?.completed_count || 0
  const totalCount = steps.length
  const pct = Math.round((completedCount / totalCount) * 100)

  return (
    <div className="space-y-8 max-w-5xl">
      {/* Header */}
      <div className="pb-3 border-b border-slate-200/70">
        <div className="inline-flex items-center gap-2 px-2.5 py-1 rounded-full bg-gradient-to-r from-emerald-50 to-sky-50 border border-emerald-200/80 text-[11px] font-mono text-emerald-900 mb-2">
          <BookOpen size={13} className="text-emerald-600" />
          <span>Integration & Onboarding Documentation</span>
        </div>
        <h1 className="text-2xl font-bold tracking-tight text-slate-900">
          Quickstart & Agent Setup
        </h1>
        <p className="text-sm text-slate-500 mt-0.5">
          Connect your AI agents, ingest OpenTelemetry traces, and uncover optimization opportunities in minutes.
        </p>
      </div>

      {/* Onboarding Checklist Card */}
      <div className="bg-white/95 rounded-xl border border-slate-200/80 p-6 shadow-xs space-y-4">
        <div className="flex items-center justify-between pb-3 border-b border-slate-100">
          <div>
            <h2 className="text-sm font-semibold tracking-tight text-slate-900">
              Pilot Setup Progress
            </h2>
            <p className="text-xs text-slate-400 mt-0.5">
              {completedCount} of {totalCount} onboarding milestones completed ({pct}%)
            </p>
          </div>
          <div className="flex items-center gap-3">
            <button
              onClick={handleSeedDemo}
              disabled={seeding}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-mono font-medium rounded-lg bg-emerald-50 text-emerald-800 border border-emerald-200/80 hover:bg-emerald-100 disabled:opacity-50 transition-colors"
            >
              <Sparkles size={13} className="text-emerald-600" />
              {seeding ? 'Seeding traces…' : 'Seed demo data'}
            </button>
          </div>
        </div>

        {/* Progress bar */}
        <div className="w-full bg-slate-100 h-2 rounded-full overflow-hidden">
          <div
            className="bg-gradient-to-r from-emerald-500 via-teal-500 to-sky-500 h-full rounded-full transition-all duration-500"
            style={{ width: `${pct}%` }}
          ></div>
        </div>

        {/* Steps Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3 pt-2">
          {steps.map((step, idx) => (
            <div
              key={step.key}
              className={`flex items-start gap-3 p-3 rounded-lg border transition-all ${
                step.completed
                  ? 'bg-emerald-50/40 border-emerald-200/60 text-emerald-950'
                  : 'bg-slate-50/60 border-slate-200/60 text-slate-700'
              }`}
            >
              <div className="mt-0.5 shrink-0">
                {step.completed ? (
                  <CheckCircle2 size={16} className="text-emerald-600" />
                ) : (
                  <Circle size={16} className="text-slate-300" />
                )}
              </div>
              <div className="min-w-0">
                <p className="text-xs font-semibold tracking-tight">{step.title}</p>
                <p className="text-[11px] text-slate-400 mt-0.5 leading-relaxed">{step.description}</p>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Primary Ingestion Endpoint Card */}
      <div className="bg-white/95 rounded-xl border border-slate-200/80 p-6 shadow-xs space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
          <div>
            <span className="font-mono text-[11px] uppercase tracking-wider text-slate-400">Step 1 · Endpoint</span>
            <h2 className="text-base font-semibold text-slate-900 tracking-tight">OpenTelemetry Ingestion URL</h2>
          </div>
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-emerald-50 text-emerald-800 border border-emerald-200/80 font-mono text-xs">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-live-ping"></span>
            Receiver Listening
          </span>
        </div>

        <div className="flex items-center justify-between p-3.5 rounded-lg bg-slate-900 text-slate-100 font-mono text-xs overflow-x-auto border border-slate-800">
          <span className="text-emerald-400 font-semibold mr-3">POST</span>
          <span className="flex-1 select-all">{otlpEndpoint}</span>
          <button
            onClick={() => copyToClipboard(otlpEndpoint, 'endpoint')}
            className="ml-3 p-1.5 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 transition-colors shrink-0"
            title="Copy URL"
          >
            {copiedSection === 'endpoint' ? <Check size={14} className="text-emerald-400" /> : <Copy size={14} />}
          </button>
        </div>
        <p className="text-xs text-slate-500 leading-relaxed">
          AgentOptimize accepts standard OTLP/HTTP Protobuf and JSON payloads. If authentication is enabled, pass your key via standard <code className="font-mono text-xs bg-slate-100 px-1 py-0.5 rounded text-slate-800">Authorization: Bearer &lt;key&gt;</code> header.
        </p>
      </div>

      {/* Code Integration Guide with Tabs */}
      <div className="bg-white/95 rounded-xl border border-slate-200/80 p-6 shadow-xs space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-2 border-b border-slate-100">
          <div>
            <span className="font-mono text-[11px] uppercase tracking-wider text-slate-400">Step 2 · Code SDK</span>
            <h2 className="text-base font-semibold text-slate-900 tracking-tight">Agent Integration Examples</h2>
          </div>

          {/* Language / framework selector */}
          <div className="inline-flex p-1 rounded-lg bg-slate-100/90 border border-slate-200/70 gap-1 overflow-x-auto">
            {[
              { id: 'python', label: 'Python OTel' },
              { id: 'langchain', label: 'LangChain / Graph' },
              { id: 'crewai', label: 'CrewAI' },
              { id: 'curl', label: 'cURL / HTTP' },
              { id: 'docker', label: 'Docker' },
            ].map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`px-2.5 py-1 text-xs font-mono font-medium rounded-md transition-all whitespace-nowrap ${
                  activeTab === tab.id
                    ? 'bg-white text-emerald-950 font-semibold shadow-xs border border-slate-200/80'
                    : 'text-slate-600 hover:text-slate-900 hover:bg-white/50'
                }`}
              >
                {tab.label}
              </button>
            ))}
          </div>
        </div>

        {/* Code block */}
        <div className="relative rounded-lg bg-slate-900 border border-slate-800 text-slate-100 p-4 font-mono text-xs overflow-x-auto">
          <button
            onClick={() => copyToClipboard(snippets[activeTab], activeTab)}
            className="absolute top-3 right-3 p-1.5 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 transition-colors"
            title="Copy snippet"
          >
            {copiedSection === activeTab ? <Check size={14} className="text-emerald-400" /> : <Copy size={14} />}
          </button>
          <pre className="leading-relaxed whitespace-pre font-mono">{snippets[activeTab]}</pre>
        </div>
      </div>

      {/* Interactive Trace Verification Sandbox */}
      <div className="bg-white/95 rounded-xl border border-slate-200/80 p-6 shadow-xs space-y-4">
        <div className="flex items-center justify-between pb-2 border-b border-slate-100">
          <div>
            <span className="font-mono text-[11px] uppercase tracking-wider text-slate-400">Step 3 · Verification</span>
            <h2 className="text-base font-semibold text-slate-900 tracking-tight">Test Ingestion Pipeline</h2>
            <p className="text-xs text-slate-400 mt-0.5">
              Send an immediate synthetic trace to verify that the OTLP normalizer, cost attribution, and waste detectors are operational.
            </p>
          </div>
          <button
            onClick={handleSendTestTrace}
            disabled={testTraceState.loading}
            className="flex items-center gap-2 px-4 py-2 bg-gradient-to-r from-emerald-600 via-teal-600 to-sky-600 text-white rounded-lg hover:from-emerald-700 hover:to-sky-700 disabled:opacity-50 text-xs font-mono font-medium shadow-xs transition-all active:scale-[0.98]"
          >
            <Send size={13} className={testTraceState.loading ? 'animate-spin' : ''} />
            {testTraceState.loading ? 'Transmitting…' : 'Send Test Trace'}
          </button>
        </div>

        {testTraceState.result && (
          <div className="p-4 rounded-lg bg-emerald-50/80 border border-emerald-200/80 space-y-2">
            <div className="flex items-center gap-2 text-emerald-900 font-semibold text-xs font-mono">
              <CheckCircle2 size={16} className="text-emerald-600" />
              Trace Ingested & Analyzed Successfully!
            </div>
            <div className="text-xs font-mono text-emerald-800 space-y-1">
              <div>Trace ID: <span className="font-bold">{testTraceState.result.traceId}</span></div>
              <div>Status: Ingested through OTel normalizer → Cost Analyzer → Waste Detectors</div>
            </div>
            <div className="pt-1">
              <a
                href="/traces"
                className="inline-flex items-center gap-1 text-xs font-mono font-semibold text-emerald-700 hover:text-emerald-900 underline"
              >
                View in Traces Inspector <ArrowRight size={13} />
              </a>
            </div>
          </div>
        )}

        {testTraceState.error && (
          <div className="p-4 rounded-lg bg-rose-50 border border-rose-200 text-rose-800 text-xs font-mono">
            Error transmitting trace: {testTraceState.error}
          </div>
        )}
      </div>

      {/* FinOps Concepts: Detectors & Evaluators reference */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* 7 Waste Detectors */}
        <div className="bg-white/95 rounded-xl border border-slate-200/80 p-5 shadow-xs space-y-3">
          <div className="flex items-center gap-2">
            <Layers size={16} className="text-emerald-600" />
            <h3 className="font-semibold text-sm text-slate-900 tracking-tight">7 Built-in Waste Detectors</h3>
          </div>
          <ul className="space-y-2 text-xs text-slate-600">
            <li className="flex items-start gap-1.5">
              <span className="font-mono text-emerald-600 font-bold shrink-0">01.</span>
              <div><strong className="text-slate-800">Model Overprovisioning:</strong> Flags frontier models (GPT-4o, Claude 3.5 Sonnet) used for low-complexity calls.</div>
            </li>
            <li className="flex items-start gap-1.5">
              <span className="font-mono text-emerald-600 font-bold shrink-0">02.</span>
              <div><strong className="text-slate-800">Context Duplication:</strong> Identifies uncompressed context loops and redundant token re-transmission.</div>
            </li>
            <li className="flex items-start gap-1.5">
              <span className="font-mono text-emerald-600 font-bold shrink-0">03.</span>
              <div><strong className="text-slate-800">Retry Waste:</strong> Detects repeated tool failures and expensive runaway retry sequences.</div>
            </li>
            <li className="flex items-start gap-1.5">
              <span className="font-mono text-emerald-600 font-bold shrink-0">04.</span>
              <div><strong className="text-slate-800">Unnecessary Verification:</strong> Identifies redundant secondary validation on trivial calls.</div>
            </li>
            <li className="flex items-start gap-1.5">
              <span className="font-mono text-emerald-600 font-bold shrink-0">05.</span>
              <div><strong className="text-slate-800">Redundant Tool Calls:</strong> Detects identical tool calls via input hash deduplication.</div>
            </li>
            <li className="flex items-start gap-1.5">
              <span className="font-mono text-emerald-600 font-bold shrink-0">06.</span>
              <div><strong className="text-slate-800">Bad Routing:</strong> Identifies monolithic model routing where 100% of calls go to premium models.</div>
            </li>
            <li className="flex items-start gap-1.5">
              <span className="font-mono text-emerald-600 font-bold shrink-0">07.</span>
              <div><strong className="text-slate-800">Serialization Waste:</strong> Highlights independent workflow stages that can run in parallel.</div>
            </li>
          </ul>
        </div>

        {/* 6 Quality Evaluators */}
        <div className="bg-white/95 rounded-xl border border-slate-200/80 p-5 shadow-xs space-y-3">
          <div className="flex items-center gap-2">
            <ShieldCheck size={16} className="text-sky-600" />
            <h3 className="font-semibold text-sm text-slate-900 tracking-tight">6 Quality Preservation Evaluators</h3>
          </div>
          <ul className="space-y-2 text-xs text-slate-600">
            <li className="flex items-start gap-1.5">
              <span className="font-mono text-sky-600 font-bold shrink-0">01.</span>
              <div><strong className="text-slate-800">Success Rate:</strong> Verifies task success rate doesn't regress past customer tolerance.</div>
            </li>
            <li className="flex items-start gap-1.5">
              <span className="font-mono text-sky-600 font-bold shrink-0">02.</span>
              <div><strong className="text-slate-800">Latency SLA:</strong> Ensures P95 response latency remains strictly within SLA targets.</div>
            </li>
            <li className="flex items-start gap-1.5">
              <span className="font-mono text-sky-600 font-bold shrink-0">03.</span>
              <div><strong className="text-slate-800">Cost Bounds:</strong> Mathematically validates that candidate configurations produce positive net savings.</div>
            </li>
            <li className="flex items-start gap-1.5">
              <span className="font-mono text-sky-600 font-bold shrink-0">04.</span>
              <div><strong className="text-slate-800">Error Rate:</strong> Prevents tool or execution errors from spiking above baseline.</div>
            </li>
            <li className="flex items-start gap-1.5">
              <span className="font-mono text-sky-600 font-bold shrink-0">05.</span>
              <div><strong className="text-slate-800">Statistical Quality:</strong> Performs Z-test regression analysis across replay cohorts.</div>
            </li>
            <li className="flex items-start gap-1.5">
              <span className="font-mono text-sky-600 font-bold shrink-0">06.</span>
              <div><strong className="text-slate-800">Model-Based Judge:</strong> Evaluates semantic output quality and reasoning fidelity.</div>
            </li>
          </ul>
        </div>
      </div>
    </div>
  )
}
