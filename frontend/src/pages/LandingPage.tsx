import { Link } from 'react-router-dom'
import {
  ArrowRight,
  Shield,
  TrendingDown,
  FileSearch,
  BarChart3,
  Zap,
  GitCompare,
  Brain,
  Bot,
  Eye,
  CheckCircle2,
  ChevronRight,
  Activity,
  Play,
} from 'lucide-react'

/* ─── Hero stats ─── */
const heroStats = [
  { value: '$2.3M', label: 'Avg. savings detected per quarter', accent: 'text-emerald-400' },
  { value: '94%', label: 'Extraction accuracy on real calls', accent: 'text-sky-400' },
  { value: '< 3 min', label: 'From recording to structured intel', accent: 'text-violet-400' },
]

/* ─── Core capabilities ─── */
const capabilities = [
  {
    icon: TrendingDown,
    title: 'Concession Tracking',
    desc: 'Detect every concession, discount, and accommodation in real-time. Know exactly what your team is giving away — and what they are winning.',
    color: 'from-emerald-500 to-teal-600',
    bg: 'bg-emerald-500/10',
    iconColor: 'text-emerald-400',
  },
  {
    icon: Shield,
    title: 'Supplier Risk Scoring',
    desc: 'Composite risk scores from delivery signals, financial health indicators, and compliance gaps. Aggregated across every call with a supplier.',
    color: 'from-red-500 to-rose-600',
    bg: 'bg-red-500/10',
    iconColor: 'text-red-400',
  },
  {
    icon: FileSearch,
    title: 'Contract Clause Analysis',
    desc: 'Track which clauses get objected to, which are deal-breakers, and which resolve. Build institutional memory of your negotiation patterns.',
    color: 'from-amber-500 to-orange-600',
    bg: 'bg-amber-500/10',
    iconColor: 'text-amber-400',
  },
  {
    icon: BarChart3,
    title: 'Savings Calculator',
    desc: '"Your team extracted $X in concessions this quarter." Automatic ROI tracking that proves the value of your procurement function.',
    color: 'from-indigo-500 to-blue-600',
    bg: 'bg-indigo-500/10',
    iconColor: 'text-indigo-400',
  },
  {
    icon: GitCompare,
    title: 'Temporal Diff Engine',
    desc: 'Compare this quarter\'s negotiation with last quarter\'s for the same supplier. See what changed, what escalated, and what resolved.',
    color: 'from-violet-500 to-purple-600',
    bg: 'bg-violet-500/10',
    iconColor: 'text-violet-400',
  },
  {
    icon: Bot,
    title: 'Live Copilot',
    desc: 'Real-time coaching during live calls. "Supplier just mentioned capacity issues — ask about backup suppliers." Coaching that changes outcomes.',
    color: 'from-sky-500 to-cyan-600',
    bg: 'bg-sky-500/10',
    iconColor: 'text-sky-400',
  },
]

/* ─── How it works steps ─── */
const steps = [
  { num: '01', title: 'Upload or Connect', desc: 'Drop a recording, connect Zoom/Teams, or stream live. We handle mp4, webm, mkv, and live RTMP/WebRTC.' },
  { num: '02', title: 'Extract Intelligence', desc: 'AI extracts pricing signals, concessions, commitment strength, supplier risk, SLA terms, and clause objections — per segment, timestamped.' },
  { num: '03', title: 'Aggregate & Score', desc: 'Supplier scorecards, savings tracking, compliance gap alerts, and negotiation stage inference across your entire call library.' },
  { num: '04', title: 'Push to S2P', desc: 'Feed structured intelligence back into Coupa, SAP Ariba, GEP, or Jaggaer. Close the loop between negotiation and contract management.' },
]

/* ─── Differentiators ─── */
const diffPoints = [
  { title: 'Not Gong for Procurement', desc: 'Gong was built for sales reps. DealFrame was built for procurement teams — different schemas, different intelligence, different ROI story.' },
  { title: 'Your S2P Platform\'s Blind Spot', desc: 'Coupa manages contracts. SAP Ariba manages spend. Neither one analyzes the negotiation calls that produce those contracts.' },
  { title: 'Intelligence That Improves', desc: 'Active learning routes low-confidence extractions to human reviewers. Every correction makes the next extraction more accurate.' },
  { title: '26-Field Procurement Schema', desc: 'Pricing signals, concession tracking, BATNA assessment, power balance, negotiation tactics, escalation level, maverick spend — all structured, all timestamped.' },
]

export function LandingPage() {
  return (
    <div className="min-h-screen bg-[#06090F] text-white overflow-x-hidden">
      {/* ─── Navigation ─── */}
      <nav className="fixed top-0 left-0 right-0 z-50 backdrop-blur-xl bg-[#06090F]/80 border-b border-white/[0.06]">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 bg-gradient-to-br from-indigo-400 via-indigo-500 to-violet-600 rounded-lg flex items-center justify-center shadow-lg shadow-indigo-900/50">
              <Activity className="w-4 h-4 text-white" />
            </div>
            <span className="font-bold text-lg tracking-tight">DealFrame</span>
          </div>
          <div className="hidden md:flex items-center gap-8 text-sm text-slate-400">
            <a href="#capabilities" className="hover:text-white transition-colors">Capabilities</a>
            <a href="#how-it-works" className="hover:text-white transition-colors">How It Works</a>
            <a href="#why-dealframe" className="hover:text-white transition-colors">Why DealFrame</a>
          </div>
          <div className="flex items-center gap-3">
            <Link to="/dashboard" className="hidden sm:inline-flex text-sm text-slate-400 hover:text-white transition-colors px-3 py-2">
              Log In
            </Link>
            <Link
              to="/dashboard"
              className="inline-flex items-center gap-1.5 px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white text-sm font-semibold rounded-lg transition-all shadow-lg shadow-indigo-900/30"
            >
              Get Started <ArrowRight className="w-3.5 h-3.5" />
            </Link>
          </div>
        </div>
      </nav>

      {/* ─── Hero ─── */}
      <section className="relative pt-32 pb-20 sm:pt-40 sm:pb-28">
        {/* Background glow */}
        <div className="absolute inset-0 overflow-hidden">
          <div className="absolute top-20 left-1/2 -translate-x-1/2 w-[800px] h-[600px] bg-gradient-radial from-indigo-600/20 via-violet-600/10 to-transparent rounded-full blur-3xl" />
          <div className="absolute top-40 left-1/4 w-[400px] h-[400px] bg-gradient-radial from-emerald-600/10 to-transparent rounded-full blur-3xl" />
        </div>

        <div className="relative max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          {/* Badge */}
          <div className="flex justify-center mb-8">
            <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full bg-white/[0.06] border border-white/[0.08] backdrop-blur-sm">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
              <span className="text-xs font-medium text-slate-300">Procurement Intelligence Platform</span>
            </div>
          </div>

          {/* Headline */}
          <h1 className="text-center text-4xl sm:text-5xl lg:text-6xl font-extrabold tracking-tight leading-[1.1] max-w-4xl mx-auto">
            <span className="text-white">Your negotiation recordings </span>
            <span className="bg-gradient-to-r from-indigo-400 via-violet-400 to-emerald-400 bg-clip-text text-transparent">
              are sitting unused
            </span>
          </h1>

          {/* Subheadline */}
          <p className="mt-6 text-center text-lg sm:text-xl text-slate-400 max-w-2xl mx-auto leading-relaxed">
            DealFrame extracts pricing signals, concession tracking, supplier risk, and contract clause analysis from every procurement call — then feeds it back into your S2P platform.
          </p>

          {/* CTA buttons */}
          <div className="mt-10 flex flex-col sm:flex-row items-center justify-center gap-4">
            <Link
              to="/upload"
              className="inline-flex items-center gap-2 px-7 py-3.5 bg-gradient-to-r from-indigo-600 to-violet-600 hover:from-indigo-500 hover:to-violet-500 text-white font-semibold rounded-xl transition-all shadow-xl shadow-indigo-900/40 text-sm"
            >
              <Zap className="w-4 h-4" />
              Upload a Recording
            </Link>
            <a
              href="#how-it-works"
              className="inline-flex items-center gap-2 px-7 py-3.5 bg-white/[0.06] hover:bg-white/[0.1] border border-white/[0.1] text-slate-300 font-semibold rounded-xl transition-all text-sm backdrop-blur-sm"
            >
              <Play className="w-4 h-4" />
              See How It Works
            </a>
          </div>

          {/* Hero stats */}
          <div className="mt-16 grid grid-cols-1 sm:grid-cols-3 gap-6 max-w-3xl mx-auto">
            {heroStats.map(({ value, label, accent }) => (
              <div key={label} className="text-center">
                <p className={`text-3xl sm:text-4xl font-extrabold tracking-tight ${accent}`}>{value}</p>
                <p className="text-xs sm:text-sm text-slate-500 mt-1">{label}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ─── Logos / Social Proof placeholder ─── */}
      <section className="py-12 border-y border-white/[0.04]">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <p className="text-center text-xs font-semibold text-slate-600 uppercase tracking-widest mb-6">
            Built for teams using
          </p>
          <div className="flex flex-wrap items-center justify-center gap-8 sm:gap-12 opacity-40">
            {['Coupa', 'SAP Ariba', 'GEP', 'Jaggaer', 'Ivalua'].map(name => (
              <span key={name} className="text-sm sm:text-base font-bold text-slate-400 tracking-wide">{name}</span>
            ))}
          </div>
        </div>
      </section>

      {/* ─── Capabilities ─── */}
      <section id="capabilities" className="py-20 sm:py-28">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center mb-14">
            <p className="text-xs font-bold uppercase tracking-widest text-indigo-400 mb-3">Capabilities</p>
            <h2 className="text-3xl sm:text-4xl font-extrabold tracking-tight">
              Every signal, structured and timestamped
            </h2>
            <p className="mt-4 text-slate-400 max-w-xl mx-auto">
              26 procurement-specific extraction fields powered by LLMs with game-theory analysis. Not generic transcription — domain intelligence.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
            {capabilities.map(({ icon: Icon, title, desc, bg, iconColor }) => (
              <div
                key={title}
                className="group relative p-6 rounded-2xl bg-white/[0.02] border border-white/[0.06] hover:border-white/[0.12] hover:bg-white/[0.04] transition-all duration-300"
              >
                <div className={`w-10 h-10 ${bg} rounded-xl flex items-center justify-center mb-4`}>
                  <Icon className={`w-5 h-5 ${iconColor}`} />
                </div>
                <h3 className="text-base font-bold text-white mb-2">{title}</h3>
                <p className="text-sm text-slate-400 leading-relaxed">{desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ─── How It Works ─── */}
      <section id="how-it-works" className="py-20 sm:py-28 bg-gradient-to-b from-transparent via-indigo-950/20 to-transparent">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center mb-14">
            <p className="text-xs font-bold uppercase tracking-widest text-violet-400 mb-3">How It Works</p>
            <h2 className="text-3xl sm:text-4xl font-extrabold tracking-tight">
              Recording to intelligence in four steps
            </h2>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
            {steps.map(({ num, title, desc }, i) => (
              <div key={num} className="relative">
                {/* Connector line */}
                {i < steps.length - 1 && (
                  <div className="hidden lg:block absolute top-6 left-full w-full h-px bg-gradient-to-r from-white/10 to-transparent z-0" />
                )}
                <div className="relative p-6 rounded-2xl bg-white/[0.02] border border-white/[0.06]">
                  <span className="text-3xl font-extrabold bg-gradient-to-b from-white/20 to-white/5 bg-clip-text text-transparent">{num}</span>
                  <h3 className="text-base font-bold text-white mt-3 mb-2">{title}</h3>
                  <p className="text-sm text-slate-400 leading-relaxed">{desc}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ─── Product Visual / Mock ─── */}
      <section className="py-20 sm:py-28">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="relative rounded-2xl overflow-hidden border border-white/[0.08] bg-gradient-to-br from-slate-900 to-[#0a0f1e]">
            {/* Simulated dashboard preview */}
            <div className="p-6 sm:p-10">
              <div className="flex items-center gap-2 mb-6">
                <div className="w-3 h-3 rounded-full bg-red-500/60" />
                <div className="w-3 h-3 rounded-full bg-amber-500/60" />
                <div className="w-3 h-3 rounded-full bg-emerald-500/60" />
                <span className="ml-3 text-xs text-slate-600 font-mono">DealFrame — Supplier Scorecard</span>
              </div>

              <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
                {[
                  { label: 'Total Savings Detected', val: '$847K', color: 'text-emerald-400' },
                  { label: 'Avg Supplier Risk', val: '0.34', color: 'text-amber-400' },
                  { label: 'Calls Analyzed', val: '156', color: 'text-sky-400' },
                  { label: 'Compliance Gaps', val: '7', color: 'text-red-400' },
                ].map(({ label, val, color }) => (
                  <div key={label} className="p-4 rounded-xl bg-white/[0.03] border border-white/[0.06]">
                    <p className={`text-2xl font-bold ${color}`}>{val}</p>
                    <p className="text-xs text-slate-500 mt-1">{label}</p>
                  </div>
                ))}
              </div>

              {/* Simulated table */}
              <div className="rounded-xl bg-white/[0.02] border border-white/[0.06] overflow-hidden">
                <div className="grid grid-cols-5 gap-4 px-4 py-3 border-b border-white/[0.06] text-xs font-bold text-slate-500 uppercase tracking-wider">
                  <span>Supplier</span>
                  <span>Risk Score</span>
                  <span>Concessions</span>
                  <span>Stage</span>
                  <span>Commitment</span>
                </div>
                {[
                  { name: 'Acme Industrial', risk: 0.67, concessions: 3, stage: 'Final Negotiation', commit: 'weak' },
                  { name: 'GlobalParts Co', risk: 0.23, concessions: 1, stage: 'Counter Offer', commit: 'strong' },
                  { name: 'TechSupply Inc', risk: 0.45, concessions: 2, stage: 'Verbal Agreement', commit: 'mixed' },
                ].map(({ name, risk, concessions, stage, commit }) => (
                  <div key={name} className="grid grid-cols-5 gap-4 px-4 py-3 border-b border-white/[0.04] text-sm items-center">
                    <span className="text-white font-medium truncate">{name}</span>
                    <span className={`font-mono font-bold ${risk > 0.5 ? 'text-red-400' : risk > 0.3 ? 'text-amber-400' : 'text-emerald-400'}`}>
                      {risk.toFixed(2)}
                    </span>
                    <span className="text-slate-300">{concessions} detected</span>
                    <span className="text-xs px-2.5 py-1 rounded-full bg-violet-500/15 text-violet-300 font-medium w-fit">{stage}</span>
                    <span className={`text-xs font-semibold capitalize ${
                      commit === 'strong' ? 'text-emerald-400' : commit === 'weak' ? 'text-red-400' : 'text-amber-400'
                    }`}>{commit}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ─── Why DealFrame ─── */}
      <section id="why-dealframe" className="py-20 sm:py-28 bg-gradient-to-b from-transparent via-emerald-950/10 to-transparent">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center mb-14">
            <p className="text-xs font-bold uppercase tracking-widest text-emerald-400 mb-3">Why DealFrame</p>
            <h2 className="text-3xl sm:text-4xl font-extrabold tracking-tight">
              The only tool built for procurement negotiation intelligence
            </h2>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-5 max-w-4xl mx-auto">
            {diffPoints.map(({ title, desc }) => (
              <div key={title} className="flex gap-4 p-6 rounded-2xl bg-white/[0.02] border border-white/[0.06]">
                <CheckCircle2 className="w-5 h-5 text-emerald-400 flex-shrink-0 mt-0.5" />
                <div>
                  <h3 className="text-base font-bold text-white mb-1">{title}</h3>
                  <p className="text-sm text-slate-400 leading-relaxed">{desc}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ─── Schema Showcase ─── */}
      <section className="py-20 sm:py-28">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-10 items-center">
            <div>
              <p className="text-xs font-bold uppercase tracking-widest text-amber-400 mb-3">Extraction Schema</p>
              <h2 className="text-3xl sm:text-4xl font-extrabold tracking-tight mb-4">
                26 fields, purpose-built for procurement
              </h2>
              <p className="text-slate-400 leading-relaxed mb-6">
                Every segment of every call is analyzed for procurement-specific signals. Not generic "topics" and "sentiment" — real negotiation intelligence.
              </p>
              <Link to="/schema-builder" className="inline-flex items-center gap-2 text-indigo-400 hover:text-indigo-300 font-semibold text-sm transition-colors">
                Explore the schema builder <ChevronRight className="w-4 h-4" />
              </Link>
            </div>
            <div className="grid grid-cols-2 gap-3">
              {[
                'Pricing Signals', 'Concessions Offered', 'Commitment Strength', 'Supplier Risk Score',
                'Negotiation Stage', 'BATNA Assessment', 'Power Balance', 'Negotiation Tactics',
                'Clause Objections', 'SLA Commitments', 'Compliance Mentions', 'TCO Signals',
                'Escalation Level', 'Maverick Spend Risk', 'Bargaining Style', 'Issues on Table',
              ].map(field => (
                <div key={field} className="px-3 py-2.5 rounded-lg bg-white/[0.03] border border-white/[0.06] text-xs text-slate-300 font-medium">
                  {field}
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      {/* ─── CTA ─── */}
      <section className="py-20 sm:py-28">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="relative rounded-3xl overflow-hidden">
            {/* Background gradient */}
            <div className="absolute inset-0 bg-gradient-to-r from-indigo-600 via-violet-600 to-purple-700" />
            <div className="absolute inset-0 bg-[url('data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iNjAiIGhlaWdodD0iNjAiIHZpZXdCb3g9IjAgMCA2MCA2MCIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj48ZyBmaWxsPSJub25lIiBmaWxsLXJ1bGU9ImV2ZW5vZGQiPjxnIGZpbGw9IiNmZmZmZmYiIGZpbGwtb3BhY2l0eT0iMC4wMyI+PHBhdGggZD0iTTM2IDM0djZoNnYtNmgtNnptMCAwdi02aC02djZoNnoiLz48L2c+PC9nPjwvc3ZnPg==')] opacity-50" />

            <div className="relative px-8 py-16 sm:px-16 sm:py-20 text-center">
              <h2 className="text-3xl sm:text-4xl font-extrabold tracking-tight text-white mb-4">
                Stop leaving negotiation intelligence on the table
              </h2>
              <p className="text-indigo-200 text-lg max-w-xl mx-auto mb-8">
                Upload your first recording and see structured procurement intelligence in under 3 minutes.
              </p>
              <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
                <Link
                  to="/upload"
                  className="inline-flex items-center gap-2 px-8 py-4 bg-white text-indigo-700 font-bold rounded-xl hover:bg-indigo-50 transition-all shadow-xl text-sm"
                >
                  <Zap className="w-4 h-4" />
                  Start Free
                </Link>
                <Link
                  to="/dashboard"
                  className="inline-flex items-center gap-2 px-8 py-4 bg-white/10 hover:bg-white/20 text-white font-semibold rounded-xl transition-all border border-white/20 text-sm backdrop-blur-sm"
                >
                  <Eye className="w-4 h-4" />
                  View Demo Dashboard
                </Link>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ─── Footer ─── */}
      <footer className="py-12 border-t border-white/[0.06]">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex flex-col md:flex-row items-center justify-between gap-6">
            <div className="flex items-center gap-3">
              <div className="w-7 h-7 bg-gradient-to-br from-indigo-400 to-violet-600 rounded-lg flex items-center justify-center">
                <Activity className="w-3.5 h-3.5 text-white" />
              </div>
              <span className="font-bold text-sm tracking-tight text-white">DealFrame</span>
              <span className="text-xs text-slate-600 ml-2">Procurement Intelligence</span>
            </div>
            <div className="flex items-center gap-6 text-xs text-slate-500">
              <Link to="/dashboard" className="hover:text-slate-300 transition-colors">Dashboard</Link>
              <a href="/docs" className="hover:text-slate-300 transition-colors">API Docs</a>
              <a href="https://linkedin.com/in/phani-marupaka" target="_blank" rel="noreferrer" className="hover:text-slate-300 transition-colors">LinkedIn</a>
            </div>
            <p className="text-xs text-slate-700">
              &copy; 2024-2026{' '}
              <a href="https://phanimarupaka.netlify.app" target="_blank" rel="noreferrer" className="hover:text-slate-400 transition-colors">
                Phani Marupaka
              </a>
            </p>
          </div>
        </div>
      </footer>
    </div>
  )
}
