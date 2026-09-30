import {
  Activity,
  ArrowRight,
  BarChart3,
  BookOpen,
  Check,
  CircleDollarSign,
  Code2,
  Copy,
  Gauge,
  Github,
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

const features = [
  {
    icon: CircleDollarSign,
    title: 'See where AI spend goes',
    text: 'Attribute cost across models, tools, retries, context, and agent paths—not just the final invoice.',
  },
  {
    icon: BarChart3,
    title: 'Find waste with evidence',
    text: 'Turn raw OpenTelemetry traces into ranked opportunities your team can understand and act on.',
  },
  {
    icon: ShieldCheck,
    title: 'Optimize without guesswork',
    text: 'Replay historical workloads and prove quality, latency, reliability, and savings before rollout.',
  },
]

const steps = [
  ['01', 'Observe', 'Connect OpenTelemetry and capture the full shape of every agent run.'],
  ['02', 'Diagnose', 'Detect overprovisioned models, duplicate context, retries, and redundant tools.'],
  ['03', 'Prove', 'Compare current and candidate configurations against real workloads.'],
  ['04', 'Optimize', 'Deploy changes inside the quality, SLA, and risk guardrails you define.'],
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
        <section className="marketing-hero">
          <div className="hero-copy">
            <div className="marketing-eyebrow"><span className="eyebrow-pulse" /> AI AGENT FINOPS</div>
            <h1>Make every agent run <em>count.</em></h1>
            <p className="hero-lede">AgentOptimize shows where your AI systems waste money, then proves the safest way to make them better.</p>
            <div className="hero-actions">
              <a className="primary-button" href={DEMO_MAILTO}>Request a demo <ArrowRight size={17} /></a>
              <a className="secondary-button" href="https://github.com/dheeraj7000/agent-optimize" target="_blank" rel="noreferrer"><Github size={17} /> View on GitHub</a>
            </div>
            <div className="hero-note"><Check size={15} /> Framework agnostic <span /> <Check size={15} /> OpenTelemetry native <span /> <Check size={15} /> Quality protected</div>
          </div>
          <div className="hero-visual" aria-label="AgentOptimize cost intelligence preview">
            <div className="visual-glow" />
            <div className="dashboard-card dashboard-card-main">
              <div className="mini-card-top"><span>WORKSPACE / OVERVIEW</span><span className="mini-live"><i /> LIVE</span></div>
              <div className="metric-row"><div><small>Projected monthly waste</small><strong>$12,840</strong><span className="metric-down">↓ 18.6% this month</span></div><Gauge size={42} className="metric-gauge" /></div>
              <div className="chart-bars"><i style={{ height: '42%' }} /><i style={{ height: '56%' }} /><i style={{ height: '48%' }} /><i style={{ height: '72%' }} /><i style={{ height: '61%' }} /><i style={{ height: '84%' }} /><i className="active-bar" style={{ height: '67%' }} /><i style={{ height: '91%' }} /></div>
              <div className="chart-labels"><span>W1</span><span>W2</span><span>W3</span><span>W4</span><span>W5</span><span>W6</span><span>W7</span><span>W8</span></div>
            </div>
            <div className="dashboard-card dashboard-card-float"><span className="float-icon"><Zap size={15} /></span><div><small>TOP OPPORTUNITY</small><strong>Route simple calls to a smaller model</strong><span className="float-saving">Save $3,240 / month</span></div><ArrowRight size={16} /></div>
            <div className="visual-orbit orbit-one" /><div className="visual-orbit orbit-two" />
          </div>
        </section>

        <section className="trust-strip"><span>BUILT FOR TEAMS RUNNING</span><b>LLM APPS</b><span>·</span><b>AI AGENTS</b><span>·</span><b>TOOL CHAINS</b><span>·</span><b>RAG SYSTEMS</b></section>

        <section className="marketing-section" id="product">
          <div className="section-heading"><div><div className="marketing-eyebrow">THE CONTROL PLANE FOR AI COST</div><h2>Spend less. Learn more.<br /><span>Keep the quality.</span></h2></div><p>Most AI teams can see their bill. AgentOptimize helps them understand the behavior behind it—and change that behavior safely.</p></div>
          <div className="feature-grid">{features.map(({ icon: Icon, title, text }) => <article className="feature-card" key={title}><div className="feature-icon"><Icon size={20} /></div><h3>{title}</h3><p>{text}</p><a href="#how-it-works">Explore capability <ArrowRight size={15} /></a></article>)}</div>
        </section>

        <section className="process-section" id="how-it-works">
          <div className="section-heading process-heading"><div><div className="marketing-eyebrow"><Sparkles size={13} /> FROM TRACE TO PROOF</div><h2>A feedback loop for<br /><span>better agents.</span></h2></div><p>Replace optimization debates with a measurable loop that connects engineering decisions to business outcomes.</p></div>
          <div className="steps-grid">{steps.map(([number, title, text]) => <article className="step-card" key={number}><span className="step-number">{number}</span><div className="step-line" /><h3>{title}</h3><p>{text}</p></article>)}</div>
        </section>

        {/* Self-Onboarding & Setup Documentation Section */}
        <section className="marketing-section setup-section" id="setup">
          <div className="section-heading setup-heading">
            <div>
              <div className="marketing-eyebrow"><Terminal size={13} /> SELF-ONBOARDING & SETUP</div>
              <h2>Run on your system<br /><span>in under two minutes.</span></h2>
            </div>
            <p>
              Deploy AgentOptimize inside your private VPC or developer laptop.
              Single unified port (:8080) serves both the React dashboard and OTLP ingestion pipeline. Zero prompt or telemetry data leaves your boundary.
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
                    Once booted, navigate to <code className="setup-inline-code">/app/quickstart</code> for guided onboarding. Click <strong>"Seed demo data"</strong> to populate 20+ realistic traces and see waste opportunities in 2 seconds.
                  </p>
                </div>
              </div>
              <div className="setup-interactive-actions">
                <Link to="/app/quickstart" className="setup-guide-link">
                  Open Quickstart Guide <ArrowRight size={15} />
                </Link>
              </div>
            </div>

            {/* Self-Hosting Value Pillars */}
            <div className="setup-features-grid">
              <div className="setup-feature-item">
                <div className="setup-feature-icon"><Lock size={16} /></div>
                <div>
                  <strong>Zero Data Egress</strong>
                  <p>Fully air-gapped capable. Sensitive prompts, tool arguments, and tokens remain strictly inside your VPC.</p>
                </div>
              </div>
              <div className="setup-feature-item">
                <div className="setup-feature-icon"><Server size={16} /></div>
                <div>
                  <strong>Single Port Architecture</strong>
                  <p>FastAPI mounts the React dashboard build directly. API, Web UI, and OTLP ingestion live cleanly on port 8080.</p>
                </div>
              </div>
              <div className="setup-feature-item">
                <div className="setup-feature-icon"><BookOpen size={16} /></div>
                <div>
                  <strong>OpenTelemetry Native</strong>
                  <p>Ingest traces directly via HTTP/JSON at <code className="setup-inline-code">/v1/traces</code> or via standard OTel Collector on 4317/4318.</p>
                </div>
              </div>
            </div>
          </div>
        </section>

        <section className="integration-section" id="integrations">
          <div className="integration-icon"><Code2 size={24} /></div>
          <div>
            <div className="marketing-eyebrow">INSTRUMENT ONCE. SEE EVERYTHING.</div>
            <h2>Works with the stack you already have.</h2>
            <p>AgentOptimize is built on OpenTelemetry, so your existing traces become cost, quality, and reliability intelligence without a new vendor-specific SDK.</p>
          </div>
          <a className="text-button" href={DEMO_MAILTO}>Talk to us <ArrowRight size={16} /></a>
        </section>

        <section className="final-cta">
          <div className="marketing-eyebrow">READY TO OPTIMIZE?</div>
          <h2>Your agents are already<br /><span>leaving money on the table.</span></h2>
          <p>Find it before it becomes your next infrastructure bill.</p>
          <a className="primary-button" href={DEMO_MAILTO}>Request a demo <ArrowRight size={17} /></a>
        </section>
      </main>

      <footer className="marketing-footer">
        <Link className="marketing-brand" to="/">
          <span className="marketing-brand-mark"><Activity size={16} /></span>
          <span>agent<span>optimize</span></span>
        </Link>
        <span>Observe. Diagnose. Optimize. Prove.</span>
        <div>
          <a href="#setup">Docs & Setup</a>
          <a href="https://github.com/dheeraj7000/agent-optimize" target="_blank" rel="noreferrer">GitHub</a>
          <a href={DEMO_MAILTO}>Contact (13kumardheeraj@gmail.com)</a>
        </div>
      </footer>
    </div>
  )
}

