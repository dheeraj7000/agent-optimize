import {
  Activity,
  ArrowRight,
  BarChart3,
  Check,
  CircleDollarSign,
  Code2,
  Gauge,
  Github,
  Menu,
  ShieldCheck,
  Sparkles,
  X,
  Zap,
} from 'lucide-react'
import { useState } from 'react'
import './MarketingHome.css'

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

export default function MarketingHome() {
  const [menuOpen, setMenuOpen] = useState(false)

  return (
    <div className="marketing-page">
      <header className="marketing-nav">
        <a className="marketing-brand" href="/" aria-label="AgentOptimize home">
          <span className="marketing-brand-mark"><Activity size={18} strokeWidth={2.4} /></span>
          <span>agent<span>optimize</span></span>
        </a>
        <button className="marketing-menu-button" type="button" onClick={() => setMenuOpen(!menuOpen)} aria-label="Toggle navigation">
          {menuOpen ? <X size={20} /> : <Menu size={20} />}
        </button>
        <nav className={`marketing-links ${menuOpen ? 'marketing-links-open' : ''}`}>
          <a href="#product" onClick={() => setMenuOpen(false)}>Product</a>
          <a href="#how-it-works" onClick={() => setMenuOpen(false)}>How it works</a>
          <a href="#integrations" onClick={() => setMenuOpen(false)}>Integrations</a>
          <a className="marketing-nav-cta" href="mailto:hello@agentoptimize.ai" onClick={() => setMenuOpen(false)}>Request a demo <ArrowRight size={15} /></a>
        </nav>
      </header>

      <main>
        <section className="marketing-hero">
          <div className="hero-copy">
            <div className="marketing-eyebrow"><span className="eyebrow-pulse" /> AI AGENT FINOPS</div>
            <h1>Make every agent run <em>count.</em></h1>
            <p className="hero-lede">AgentOptimize shows where your AI systems waste money, then proves the safest way to make them better.</p>
            <div className="hero-actions">
              <a className="primary-button" href="mailto:hello@agentoptimize.ai?subject=AgentOptimize%20demo">Request a demo <ArrowRight size={17} /></a>
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

        <section className="integration-section" id="integrations"><div className="integration-icon"><Code2 size={24} /></div><div><div className="marketing-eyebrow">INSTRUMENT ONCE. SEE EVERYTHING.</div><h2>Works with the stack you already have.</h2><p>AgentOptimize is built on OpenTelemetry, so your existing traces become cost, quality, and reliability intelligence without a new vendor-specific SDK.</p></div><a className="text-button" href="mailto:hello@agentoptimize.ai">Talk to us <ArrowRight size={16} /></a></section>

        <section className="final-cta"><div className="marketing-eyebrow">READY TO OPTIMIZE?</div><h2>Your agents are already<br /><span>leaving money on the table.</span></h2><p>Find it before it becomes your next infrastructure bill.</p><a className="primary-button" href="mailto:hello@agentoptimize.ai?subject=AgentOptimize%20demo">Request a demo <ArrowRight size={17} /></a></section>
      </main>

      <footer className="marketing-footer"><a className="marketing-brand" href="/"><span className="marketing-brand-mark"><Activity size={16} /></span><span>agent<span>optimize</span></span></a><span>Observe. Diagnose. Optimize. Prove.</span><div><a href="https://github.com/dheeraj7000/agent-optimize" target="_blank" rel="noreferrer">GitHub</a><a href="mailto:hello@agentoptimize.ai">Contact</a></div></footer>
    </div>
  )
}
