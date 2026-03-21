import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { FileVideo, AlertTriangle, Cpu, DollarSign, ArrowRight, RefreshCw, TrendingUp, Zap } from 'lucide-react'
import { StatCard } from '../components/StatCard'
import { Badge } from '../components/Badge'
import {
  listJobs,
  getObjections,
  getRiskSummary,
  getLocalStatus,
  type Job,
  type Objection,
  type RiskSummary,
  type LocalStatus,
} from '../api/client'

export function Dashboard() {
  const [jobs, setJobs] = useState<Job[]>([])
  const [objections, setObjections] = useState<Objection[]>([])
  const [riskSummary, setRiskSummary] = useState<RiskSummary | null>(null)
  const [localStatus, setLocalStatus] = useState<LocalStatus | null>(null)
  const [loading, setLoading] = useState(true)

  const load = () => {
    setLoading(true)
    Promise.allSettled([
      listJobs().then(r => {
        const raw = r.jobs
        const arr = Array.isArray(raw)
          ? raw
          : Object.entries(raw ?? {}).map(([id, v]: [string, any]) => ({ id, ...v }))
        setJobs(arr)
      }).catch(() => {}),
      getObjections(5).then(r => setObjections(r.objections ?? [])).catch(() => {}),
      getRiskSummary().then(setRiskSummary).catch(() => {}),
      getLocalStatus().then(setLocalStatus).catch(() => {}),
    ]).finally(() => setLoading(false))
  }

  useEffect(() => { load() }, [])

  const completedJobs = jobs.filter(j => j.status === 'completed').length
  const highRisk = riskSummary?.high ?? 0

  return (
    <div className="p-8 animate-fade-in">
      {/* Hero header */}
      <div className="relative mb-8 bg-gradient-to-br from-indigo-600 via-indigo-700 to-violet-800 rounded-2xl p-7 overflow-hidden shadow-lg shadow-indigo-900/20">
        <div className="absolute inset-0 bg-[url('data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iNjAiIGhlaWdodD0iNjAiIHZpZXdCb3g9IjAgMCA2MCA2MCIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj48ZyBmaWxsPSJub25lIiBmaWxsLXJ1bGU9ImV2ZW5vZGQiPjxnIGZpbGw9IiNmZmZmZmYiIGZpbGwtb3BhY2l0eT0iMC4wMyI+PHBhdGggZD0iTTM2IDM0djZoNnYtNmgtNnptMCAwdi02aC02djZoNnoiLz48L2c+PC9nPjwvc3ZnPg==')] opacity-50" />
        <div className="relative flex items-start justify-between">
          <div>
            <div className="flex items-center gap-2.5 mb-2">
              <div className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
              <span className="text-xs font-semibold text-indigo-200 uppercase tracking-widest">Live Dashboard</span>
            </div>
            <h1 className="text-2xl font-bold text-white tracking-tight">Decision Intelligence</h1>
            <p className="text-indigo-200 text-sm mt-1">Video → structured signals, risks, and objections</p>
          </div>
          <div className="flex items-center gap-2.5">
            <button
              onClick={load}
              className="flex items-center gap-1.5 px-3.5 py-2 bg-white/10 hover:bg-white/20 text-white text-sm font-semibold rounded-xl transition-all border border-white/20 backdrop-blur-sm"
              disabled={loading}
            >
              <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
              Refresh
            </button>
            <Link to="/upload" className="flex items-center gap-1.5 px-3.5 py-2 bg-white text-indigo-700 text-sm font-bold rounded-xl hover:bg-indigo-50 transition-all shadow-sm">
              <FileVideo className="w-3.5 h-3.5" />
              Upload Video
            </Link>
          </div>
        </div>
        {/* Mini stats inline */}
        <div className="relative mt-6 flex items-center gap-6">
          {[
            { label: 'Videos Processed', value: completedJobs, icon: FileVideo },
            { label: 'High Risk', value: highRisk, icon: AlertTriangle },
            { label: 'Pipeline', value: localStatus?.active_extractor ?? '—', icon: Cpu },
          ].map(({ label, value, icon: Icon }) => (
            <div key={label} className="flex items-center gap-2">
              <Icon className="w-4 h-4 text-indigo-300" />
              <div>
                <p className="text-xl font-bold text-white tabular-nums leading-none">{value}</p>
                <p className="text-[11px] text-indigo-300">{label}</p>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Stat cards */}
      <div className="grid grid-cols-4 gap-4 mb-8">
        <StatCard
          label="Videos Processed"
          value={completedJobs}
          icon={FileVideo}
          iconBg="bg-indigo-50"
          iconColor="text-indigo-600"
        />
        <StatCard
          label="High Risk Segments"
          value={highRisk}
          icon={AlertTriangle}
          iconBg={highRisk > 0 ? 'bg-red-50' : 'bg-slate-50'}
          iconColor={highRisk > 0 ? 'text-red-500' : 'text-slate-400'}
          trendPositive={highRisk === 0}
        />
        <StatCard
          label="Active Extractor"
          value={localStatus?.active_extractor ?? '—'}
          icon={Cpu}
          iconBg="bg-slate-100"
          iconColor="text-slate-600"
          trend={localStatus?.finetuned_adapter_available ? 'Fine-tuned' : undefined}
          trendPositive={localStatus?.finetuned_adapter_available}
        />
        <StatCard
          label="API Cost This Session"
          value="$0.00"
          icon={DollarSign}
          iconBg="bg-emerald-50"
          iconColor="text-emerald-600"
          trend="Local pipeline"
          trendPositive
        />
      </div>

      {/* Bottom grid */}
      <div className="grid grid-cols-3 gap-6">
        {/* Recent jobs */}
        <div className="col-span-2 card overflow-hidden">
          <div className="flex items-center justify-between px-5 py-4 border-b border-slate-100">
            <h2 className="text-sm font-bold text-slate-900">Recent Jobs</h2>
            <Link to="/upload" className="text-xs text-indigo-600 hover:text-indigo-700 flex items-center gap-1 font-semibold">
              New upload <ArrowRight className="w-3 h-3" />
            </Link>
          </div>
          {jobs.length === 0 ? (
            <div className="px-5 py-12 text-center">
              <div className="w-14 h-14 bg-slate-100 rounded-2xl flex items-center justify-center mx-auto mb-3">
                <FileVideo className="w-7 h-7 text-slate-300" />
              </div>
              <p className="text-sm font-semibold text-slate-500">No videos processed yet</p>
              <p className="text-xs text-slate-400 mt-1">Upload a sales call or demo to get started</p>
              <Link to="/upload" className="inline-flex items-center gap-1 text-sm text-indigo-600 hover:text-indigo-700 font-semibold mt-3">
                Upload your first video <ArrowRight className="w-3.5 h-3.5" />
              </Link>
            </div>
          ) : (
            <div className="divide-y divide-slate-100">
              {jobs.slice(0, 8).map(job => (
                <Link
                  key={job.job_id}
                  to={`/results/${job.job_id}`}
                  className="flex items-center justify-between px-5 py-3.5 hover:bg-slate-50 transition-colors group"
                >
                  <div className="flex items-center gap-3 min-w-0">
                    <div className="w-8 h-8 bg-indigo-50 rounded-lg flex items-center justify-center flex-shrink-0">
                      <FileVideo className="w-4 h-4 text-indigo-500" />
                    </div>
                    <span className="text-sm text-slate-700 font-mono truncate">
                      {job.job_id.slice(0, 16)}…
                    </span>
                  </div>
                  <div className="flex items-center gap-3 flex-shrink-0">
                    <Badge label={job.status} />
                    <ArrowRight className="w-3.5 h-3.5 text-slate-300 group-hover:text-slate-500 group-hover:translate-x-0.5 transition-all" />
                  </div>
                </Link>
              ))}
            </div>
          )}
        </div>

        {/* Top objections */}
        <div className="card overflow-hidden">
          <div className="flex items-center justify-between px-5 py-4 border-b border-slate-100">
            <h2 className="text-sm font-bold text-slate-900">Top Objections</h2>
            <Link to="/intelligence" className="text-xs text-indigo-600 hover:text-indigo-700 font-semibold">
              View all
            </Link>
          </div>
          {objections.length === 0 ? (
            <div className="px-5 py-12 text-center">
              <div className="w-12 h-12 bg-slate-100 rounded-2xl flex items-center justify-center mx-auto mb-3">
                <TrendingUp className="w-6 h-6 text-slate-300" />
              </div>
              <p className="text-sm font-semibold text-slate-400">No data yet</p>
              <p className="text-xs text-slate-300 mt-1">Process videos to see patterns</p>
            </div>
          ) : (
            <div className="p-5 space-y-4">
              {objections.map((obj, i) => (
                <div key={i}>
                  <div className="flex items-center justify-between text-xs mb-1.5">
                    <span className="text-slate-700 truncate pr-3 font-semibold">{obj.text}</span>
                    <span className="text-slate-400 flex-shrink-0 tabular-nums font-bold">×{obj.count}</span>
                  </div>
                  <div className="h-1.5 bg-slate-100 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-gradient-to-r from-indigo-400 to-indigo-600 rounded-full transition-all"
                      style={{
                        width: `${Math.min(100, (obj.count / (objections[0]?.count || 1)) * 100)}%`,
                      }}
                    />
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Quick actions */}
      <div className="mt-6 grid grid-cols-3 gap-4">
        {[
          {
            to: '/observatory',
            label: 'Compare Models',
            sub: 'Run multi-model analysis',
            icon: TrendingUp,
            color: 'from-violet-500 to-purple-600',
            bg: 'bg-violet-50 border-violet-200 hover:border-violet-300 hover:bg-violet-50',
            iconBg: 'bg-violet-100',
            iconColor: 'text-violet-600',
          },
          {
            to: '/intelligence',
            label: 'View Intelligence',
            sub: 'Objections & trends',
            icon: TrendingUp,
            color: 'from-indigo-500 to-indigo-600',
            bg: 'bg-indigo-50 border-indigo-200 hover:border-indigo-300 hover:bg-indigo-50',
            iconBg: 'bg-indigo-100',
            iconColor: 'text-indigo-600',
          },
          {
            to: '/local',
            label: 'Local Pipeline',
            sub: 'Zero API cost processing',
            icon: Zap,
            color: 'from-emerald-500 to-green-600',
            bg: 'bg-emerald-50 border-emerald-200 hover:border-emerald-300 hover:bg-emerald-50',
            iconBg: 'bg-emerald-100',
            iconColor: 'text-emerald-600',
          },
        ].map(({ to, label, sub, icon: Icon, bg, iconBg, iconColor }) => (
          <Link
            key={to}
            to={to}
            className={`flex items-center gap-4 border rounded-2xl p-4 transition-all duration-200 hover:shadow-sm group ${bg}`}
          >
            <div className={`w-10 h-10 ${iconBg} rounded-xl flex items-center justify-center flex-shrink-0`}>
              <Icon className={`w-5 h-5 ${iconColor}`} />
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-bold text-slate-900">{label}</p>
              <p className="text-xs text-slate-500 mt-0.5">{sub}</p>
            </div>
            <ArrowRight className="w-4 h-4 text-slate-400 group-hover:text-slate-600 group-hover:translate-x-0.5 transition-all flex-shrink-0" />
          </Link>
        ))}
      </div>
    </div>
  )
}
