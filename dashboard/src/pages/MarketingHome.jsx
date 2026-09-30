import {
  Activity,
  AlertTriangle,
  ArrowRight,
  BookOpen,
  Check,
  CheckCircle2,
  CircleDollarSign,
  Code2,
  Copy,
  Cpu,
  ExternalLink,
  Github,
  Layers,
  Lock,
  Menu,
  Server,
  ShieldCheck,
  Sparkles,
  Terminal,
  X,
  Zap,
} from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router-dom'
import './MarketingHome.css'

const DEMO_MAILTO =
  'mailto:13kumardheeraj@gmail.com?subject=AgentOptimize%20Demo%20Request&body=Hi%20Dheeraj%2C%0A%0AI%20would%20like%20to%20request%20a%20demo%20of%20AgentOptimize.%0A%0AName%3A%20%0ACompany%2FProject%3A%20%0AAgent%20Frameworks%20Used%20(e.g.%20LangGraph%2C%20CrewAI%2C%20custom)%3A%20%0AEstimated%20Monthly%20AI%20Spend%3A%20%0A%0AThanks!'

const frameworks = [
  'LangChain',
  'LangGraph',
  'CrewAI',
  'Microsoft AutoGen',
  'LlamaIndex',
  'LiteLLM',
  'OpenAI Swarm',
  'OpenTelemetry OTLP',
]

const features = [
  {
    icon: Layers,
    title: 'Granular Step & Tool Attribution',
    text: 'Attribute AI cost down to individual agent spans, tool calls, context injections, and retries—not just your monthly LLM invoice.',
    detail: 'Computes exact input/output tokens, cache hits, and duration per step.',
  },
  {
    icon: Zap,
    title: '7 Algorithmic Waste Detectors',
    text: 'Continuous detectors scan every trace for model overprovisioning, duplicate context loops, redundant tool calls, and monolithic routing.',
    detail: 'Includes statistical confidence scores, evidence traces, and net dollar savings.',
  },
  {
    icon: ShieldCheck,
    title: 'Quality-Guarded Replay Engine',
    text: 'Never push routing changes blindly. Replay historical production traffic through candidate models and verify output quality against 6 SLA evaluators.',
    detail: 'Enforces success rate, semantic judge scores, and P95 latency bounds.',
  },
]

const steps = [
  ['01', 'Ingest via OpenTelemetry', 'Stream traces directly via standard OTLP/HTTP (/v1/traces) or collector. Zero vendor SDK lock-in.'],
  ['02', 'Detect Systematic Waste', 'Seven deterministic detectors surface overprovisioned models, retry cascades, and token bloat with dollar impact.'],
  ['03', 'Counterfactual Replay', 'Simulate proposed routing and prompt changes against past production cohorts to prove safety.'],
  ['04', 'Automated Guardrails', 'Enforce budget policies and automated routing with circuit breakers that halt regressions instantly.'],
]

const setupOptions = [
  {
    id: 'compose',
    title: 'Docker Compose',
    badge: 'Recommended',
    description: 'Launches AgentOptimize and the OpenTelemetry Collector sidecar with persistent volume storage in one command.',
    command: 'docker compose up -d',
    snippet: `# 1. Clone the repository
git clone https://github.com/dheeraj7000/agent-optimize.git
cd agent-optimize

# 2. Boot AgentOptimize + OTel Collector sidecar
docker compose up -d

# 3. Access web dashboard & API
# Dashboard UI: http://localhost:8080
# Trace Ingestion: http://localhost:8080/v1/traces
# OTel Collector gRPC / HTTP: 4317 / 4318`,
  },
  {
    id: 'docker',
    title: 'Standalone Docker',
    badge: 'Self-Contained',
    description: 'Multi-stage production container bundling both the React UI and Python FinOps engine on port 8080.',
    command: 'docker build -f Dockerfile.production -t agentoptimize .',
    snippet: `# 1. Build the production image (includes UI + backend)
docker build -f Dockerfile.production -t agentoptimize .

# 2. Run with persistent volume storage
docker run -d \\
  --name agentoptimize \\
  -p 8080:8080 \\
  -v agent-data:/data \\
  -e AGENTOPTIMIZE_DB_PATH=/data/agentoptimize.db \\
  -e AGENTOPTIMIZE_API_KEY_REQUIRED=false \\
  agentoptimize

# Open http://localhost:8080 in your browser`,
  },
  {
    id: 'pip',
    title: 'Python (pip)',
    badge: 'Local Dev',
    description: 'Install directly into your Python 3.11+ environment with zero container overhead.',
    command: 'pip install -e ".[dev]" && agent-optimize serve',
    snippet: `# 1. Clone & install
git clone https://github.com/dheeraj7000/agent-optimize.git
cd agent-optimize
pip install -e ".[dev]"

# 2. Start the server (hosts API + Web UI on port 8080)
agent-optimize serve

# Open http://localhost:8080 in your browser`,
  },
  {
    id: 'traces',
    title: 'Connect Telemetry',
    badge: 'OTel Native',
    description: 'Stream traces from LangChain, LangGraph, CrewAI, AutoGen, or custom agents with standard OpenTelemetry.',
    command: 'export OTEL_EXPORTER_OTLP_ENDPOINT="http://localhost:8080"',
    snippet: `# Python OpenTelemetry SDK:
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

provider = TracerProvider()
exporter = OTLPSpanExporter(endpoint="http://localhost:8080/v1/traces")
provider.add_span_processor(BatchSpanProcessor(exporter))

# Or set standard environment variables for LangChain / LangGraph / CrewAI:
# export OTEL_EXPORTER_OTLP_ENDPOINT="http://localhost:8080"
# export OTEL_EXPORTER_OTLP_PROTOCOL="http/protobuf"
# export OTEL_SERVICE_NAME="customer-support-agent"`,
  },
]

export default function MarketingHome() {
  const [menuOpen, setMenuOpen] = useState(false)
  const [activeSetupTab, setActiveSetupTab] = useState('compose')
  const [copiedId, setCopiedId] = useState(null)

  const activeOption = setupOptions.find((opt) => opt.id === activeSetupTab) || setupOptions[0]

  const handleCopy = (text, id) => {
    navigator.clipboard.writeText(text)
    setCopiedId(id)
    setTimeout(() => setCopiedId(null), 2000)
  }

  return (
    <div className="marketing-page">
      <header className="marketing-nav">
        <Link className="marketing-brand" to="/" aria-label="AgentOptimize home">
          <span className="marketing-brand-mark"><Activity size={18} strokeWidth={2.4} /></span>
          <span>agent<span>optimize</span></span>
        </Link>
        <button className="marketing-menu-button" type="button" onClick={() => setMenuOpen(!menuOpen)} aria-label="Toggle navigation">
          {menuOpen ? <X size={20} /> : <Menu size={20} />}
        </button>
        <nav className={`marketing-links ${menuOpen ? 'marketing-links-open' : ''}`}>
          <a href="#product" onClick={() => setMenuOpen(false)}>Product</a>
          <a href="#how-it-works" onClick={() => setMenuOpen(false)}>How it works</a>
          <a href="#setup" onClick={() => setMenuOpen(false)}>Docs & Setup</a>
          <a href="#integrations" onClick={() => setMenuOpen(false)}>Integrations</a>
          <Link to="/app" onClick={() => setMenuOpen(false)}>Dashboard</Link>
          <a className="marketing-nav-cta" href={DEMO_MAILTO} onClick={() => setMenuOpen(false)}>
            Request a demo <ArrowRight size={15} />
          </a>
        </nav>
      </header>

      <main>
        {/* Hero Section */}
        <section className="marketing-hero">
          <div className="hero-copy">
            <div className="marketing-eyebrow">
              <span className="eyebrow-pulse" /> OPEN-SOURCE AI AGENT FINOPS
            </div>
            <h1>
              Stop burning budget on <em>overprovisioned</em> AI agents.
            </h1>
            <p className="hero-lede">
              AgentOptimize ingests OpenTelemetry traces across your agent workflows, isolates model waste and context bloat, and proves cost reductions with offline counterfactual replay.
            </p>
            <div className="hero-actions">
              <a className="primary-button" href="#setup">
                Deploy in 2 Minutes <ArrowRight size={16} />
              </a>
              <a className="secondary-button" href={DEMO_MAILTO}>
                Request a demo
              </a>
              <a className="secondary-button" href="https://github.com/dheeraj7000/agent-optimize" target="_blank" rel="noreferrer">
                <Github size={16} /> GitHub
              </a>
            </div>
            <div className="hero-note">
              <span><Check size={14} className="text-emerald-400" /> Native OpenTelemetry (OTLP)</span>
              <span className="note-sep">·</span>
              <span><Check size={14} className="text-emerald-400" /> 100% Self-Hosted & Air-Gapped</span>
              <span className="note-sep">·</span>
              <span><Check size={14} className="text-emerald-400" /> Zero Proprietary SDKs</span>
            </div>
          </div>

          {/* High-Fidelity Trace & Waste Inspector Preview */}
          <div className="hero-visual" aria-label="AgentOptimize Trace & Waste Inspector">
            <div className="hero-trace-window">
              <div className="trace-window-topbar">
                <div className="trace-window-dots">
                  <span className="dot dot-red" />
                  <span className="dot dot-yellow" />
                  <span className="dot dot-green" />
                </div>
                <div className="trace-window-title">
                  trace_id: <span className="highlight-text">run_8f29c4</span> · support_workflow.chat
                </div>
                <div className="trace-status-pill">
                  <span className="pulse-dot" /> LIVE INGESTION
                </div>
              </div>

              {/* FinOps KPI Summary Strip */}
              <div className="trace-stats-row">
                <div className="trace-stat-box">
                  <small>BASELINE COST</small>
                  <strong>$0.0482</strong>
                  <span className="stat-sub">4,240 tokens · 1.4s</span>
                </div>
                <div className="trace-stat-box highlight-stat">
                  <small>IDENTIFIED WASTE</small>
                  <strong className="text-savings">$0.0394</strong>
                  <span className="stat-savings">↓ 81.7% avoidable spend</span>
                </div>
                <div className="trace-stat-box">
                  <small>OPTIMAL ROUTE</small>
                  <strong>GPT-4o-mini</strong>
                  <span className="stat-sub">Passes 99.2% Quality SLA</span>
                </div>
              </div>

              {/* Execution Waterfall */}
              <div className="trace-waterfall-tree">
                <div className="trace-tree-header">
                  <span>EXECUTION SPANS & DETECTIONS</span>
                  <span>LATENCY / COST</span>
                </div>

                {/* Span 1 */}
                <div className="trace-span-row">
                  <div className="span-info">
                    <span className="span-badge badge-optimal">✓ Router</span>
                    <span className="span-name">router.classify_intent</span>
                    <span className="span-model">gpt-4o-mini</span>
                  </div>
                  <div className="span-timing">
                    <span className="span-bar bar-router" style={{ width: '38px' }} />
                    <span className="span-cost">112ms · $0.0003</span>
                  </div>
                </div>

                {/* Span 2 */}
                <div className="trace-span-row">
                  <div className="span-info">
                    <span className="span-badge badge-tool">✓ Tool</span>
                    <span className="span-name">tools.vector_search</span>
                    <span className="span-model">pinecone · 4 docs</span>
                  </div>
                  <div className="span-timing">
                    <span className="span-bar bar-tool" style={{ width: '28px' }} />
                    <span className="span-cost">84ms · $0.0000</span>
                  </div>
                </div>

                {/* Span 3: Overprovisioned Frontier Call */}
                <div className="trace-span-row span-row-waste">
                  <div className="span-info">
                    <span className="span-badge badge-waste">⚠️ Waste Flag</span>
                    <span className="span-name">agent.synthesize_response</span>
                    <span className="span-model text-rose-300">gpt-4o (Frontier Model)</span>
                  </div>
                  <div className="span-timing">
                    <span className="span-bar bar-waste" style={{ width: '135px' }} />
                    <span className="span-cost text-rose-300">1,210ms · $0.0461</span>
                  </div>
                </div>

                {/* Anomaly Callout Box */}
                <div className="trace-anomaly-callout">
                  <div className="callout-header">
                    <AlertTriangle size={13} className="text-amber-400" />
                    <strong>Detector: Model Overprovisioning (Confidence: 94%)</strong>
                  </div>
                  <p>
                    Task complexity score is 0.18 (simple retrieval formatting). Replaying against <strong>GPT-4o-mini</strong> retains 99.4% intent match while cutting cost from $0.0461 to $0.0033.
                  </p>
                  <div className="callout-footer">
                    <span>Projected monthly savings: <strong>$3,240 / month</strong></span>
                    <span className="badge-tag">SLA verified</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* Framework Compatibility Strip */}
        <section className="frameworks-strip">
          <div className="frameworks-container">
            <span className="frameworks-label">NATIVE OPENTELEMETRY SUPPORT FOR:</span>
            <div className="frameworks-list">
              {frameworks.map((fw, idx) => (
                <span key={fw} className="framework-badge">
                  {fw}
                  {idx < frameworks.length - 1 && <span className="framework-dot">·</span>}
                </span>
              ))}
            </div>
          </div>
        </section>

        {/* Product / Features Section */}
        <section className="marketing-section" id="product">
          <div className="section-heading">
            <div>
              <div className="marketing-eyebrow">OBSERVE · ATTRIBUTE · OPTIMIZE</div>
              <h2>Built for engineering teams running<br /><span>agents in production.</span></h2>
            </div>
            <p>
              Most teams only see aggregated cloud invoices at the end of the month. AgentOptimize provides step-level FinOps intelligence and automated quality validation.
            </p>
          </div>
          <div className="feature-grid">
            {features.map(({ icon: Icon, title, text, detail }) => (
              <article className="feature-card" key={title}>
                <div className="feature-icon"><Icon size={20} /></div>
                <h3>{title}</h3>
                <p>{text}</p>
                <div className="feature-detail">
                  <CheckCircle2 size={13} className="text-emerald-400" />
                  <span>{detail}</span>
                </div>
              </article>
            ))}
          </div>
        </section>

        {/* Lifecycle / Process Section */}
        <section className="process-section" id="how-it-works">
          <div className="section-heading process-heading">
            <div>
              <div className="marketing-eyebrow"><Sparkles size={13} /> CONTINUOUS FINOPS LIFECYCLE</div>
              <h2>From raw traces to<br /><span>proven dollar savings.</span></h2>
            </div>
            <p>
              Replace intuition and risky prompt tweaks with a measurable evaluation loop grounded in your actual production traffic.
            </p>
          </div>
          <div className="steps-grid">
            {steps.map(([number, title, text]) => (
              <article className="step-card" key={number}>
                <span className="step-number">{number}</span>
                <div className="step-line" />
                <h3>{title}</h3>
                <p>{text}</p>
              </article>
            ))}
          </div>
        </section>

        {/* Self-Onboarding & Setup Documentation Section */}
        <section className="marketing-section setup-section" id="setup">
          <div className="section-heading setup-heading">
            <div>
              <div className="marketing-eyebrow"><Terminal size={13} /> ZERO-FRICTION SETUP</div>
              <h2>Self-host on your own infrastructure<br /><span>in under two minutes.</span></h2>
            </div>
            <p>
              Deploy AgentOptimize entirely within your private VPC or laptop.
              A single port (:8080) serves the React dashboard and OTLP ingestion pipeline. No telemetry or prompt data ever leaves your boundary.
            </p>
          </div>

          <div className="setup-container">
            {/* Setup Tabs */}
            <div className="setup-tabs">
              {setupOptions.map((opt) => (
                <button
                  key={opt.id}
                  type="button"
                  onClick={() => setActiveSetupTab(opt.id)}
                  className={`setup-tab-btn ${activeSetupTab === opt.id ? 'setup-tab-active' : ''}`}
                >
                  <span className="setup-tab-title">{opt.title}</span>
                  <span className="setup-tab-badge">{opt.badge}</span>
                </button>
              ))}
            </div>

            {/* Active Tab Panel */}
            <div className="setup-panel">
              <div className="setup-panel-header">
                <div>
                  <h3 className="setup-panel-title">{activeOption.title}</h3>
                  <p className="setup-panel-desc">{activeOption.description}</p>
                </div>
                <button
                  type="button"
                  onClick={() => handleCopy(activeOption.snippet, activeOption.id)}
                  className="setup-copy-btn"
                  title="Copy snippet"
                >
                  {copiedId === activeOption.id ? (
                    <>
                      <Check size={14} className="text-emerald-400" />
                      <span>Copied!</span>
                    </>
                  ) : (
                    <>
                      <Copy size={14} />
                      <span>Copy Code</span>
                    </>
                  )}
                </button>
              </div>

              <div className="setup-code-wrapper">
                <pre className="setup-code-block">{activeOption.snippet}</pre>
              </div>
            </div>

            {/* Quickstart Callout Card */}
            <div className="setup-interactive-card">
              <div className="setup-interactive-left">
                <div className="setup-interactive-icon">
                  <Sparkles size={20} />
                </div>
                <div>
                  <h4>Interactive In-App Quickstart Checklist</h4>
                  <p>
                    Once booted, navigate to{' '}
                    <a
                      href="http://localhost:8080/app/quickstart"
                      target="_blank"
                      rel="noreferrer"
                      className="setup-inline-code hover:underline"
                    >
                      http://localhost:8080/app/quickstart
                    </a>{' '}
                    for guided onboarding. Click <strong>"Seed demo data"</strong> to populate 20+ realistic traces and see waste opportunities in 2 seconds.
                  </p>
                </div>
              </div>
              <div className="setup-interactive-actions">
                <a
                  href="http://localhost:8080/app/quickstart"
                  target="_blank"
                  rel="noreferrer"
                  className="setup-guide-link"
                >
                  Open Quickstart Guide <ArrowRight size={15} />
                </a>
                <Link to="/app/quickstart" className="setup-preview-link">
                  Web Preview
                </Link>
              </div>
            </div>

            {/* Self-Hosting Value Pillars */}
            <div className="setup-features-grid">
              <div className="setup-feature-item">
                <div className="setup-feature-icon"><Lock size={16} /></div>
                <div>
                  <strong>Zero Data Egress</strong>
                  <p>Air-gapped capable. Sensitive prompts, tool arguments, and tokens remain strictly inside your private network.</p>
                </div>
              </div>
              <div className="setup-feature-item">
                <div className="setup-feature-icon"><Server size={16} /></div>
                <div>
                  <strong>Unified Port Architecture</strong>
                  <p>FastAPI mounts the React dashboard bundle directly. API, Web UI, and OTLP ingestion live cleanly on port 8080.</p>
                </div>
              </div>
              <div className="setup-feature-item">
                <div className="setup-feature-icon"><BookOpen size={16} /></div>
                <div>
                  <strong>OpenTelemetry Native</strong>
                  <p>Ingest traces directly via HTTP/JSON at <code className="setup-inline-code">/v1/traces</code> or standard OTel Collector on 4317/4318.</p>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* Integration Callout */}
        <section className="integration-section" id="integrations">
          <div className="integration-icon"><Code2 size={24} /></div>
          <div>
            <div className="marketing-eyebrow">STANDARD PROTOCOLS ONLY</div>
            <h2>Works with the observability stack you already run.</h2>
            <p>
              AgentOptimize speaks standard OTLP/HTTP and OTLP/gRPC. Point your existing LangChain, CrewAI, or Python tracing exporters to your self-hosted receiver without modifying business logic.
            </p>
          </div>
          <a className="text-button" href={DEMO_MAILTO}>Talk to engineering <ArrowRight size={16} /></a>
        </section>

        {/* Final CTA */}
        <section className="final-cta">
          <div className="marketing-eyebrow">TAKE CONTROL OF AI SPEND</div>
          <h2>Ready to audit your AI agent infrastructure?</h2>
          <p>
            Clone the repository, boot the container, and inspect your first trace in under two minutes.
          </p>
          <div className="final-cta-buttons">
            <a className="primary-button" href="#setup">
              Get Started with Docker <ArrowRight size={16} />
            </a>
            <a className="secondary-button" href={DEMO_MAILTO}>
              Request a demo
            </a>
          </div>
        </section>
      </main>

      <footer className="marketing-footer">
        <Link className="marketing-brand" to="/">
          <span className="marketing-brand-mark"><Activity size={16} /></span>
          <span>agent<span>optimize</span></span>
        </Link>
        <span className="footer-tagline">Open-source AI Agent FinOps · Observe. Diagnose. Optimize. Prove.</span>
        <div className="footer-links">
          <a href="#setup">Docs & Setup</a>
          <a href="https://github.com/dheeraj7000/agent-optimize" target="_blank" rel="noreferrer">GitHub</a>
          <a href={DEMO_MAILTO}>Contact (13kumardheeraj@gmail.com)</a>
        </div>
      </footer>
    </div>
  )
}


