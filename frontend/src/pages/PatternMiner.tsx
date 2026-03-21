import { useState, useEffect } from 'react'
import { TrendingUp, BarChart3, Layers, Filter, AlertTriangle, Lightbulb, Target } from 'lucide-react'
import { getPatterns, getPatternSummary } from '../api/client'

export function PatternMiner() {
  const [patterns, setPatterns] = useState<unknown[]>([])
  const [summary, setSummary] = useState<{ total_jobs: number; completed_jobs: number; total_segments: number; available_patterns: string[] } | null>(null)
  const [patternType, setPatternType] = useState('objection_risk')
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const load = async () => {
      setLoading(true)
      try {
        const [pRes, sRes] = await Promise.all([
          getPatterns(patternType),
          getPatternSummary(),
        ])
        setPatterns(pRes.patterns ?? [])
        setSummary(sRes)
      } catch { /* ignore */ }
      setLoading(false)
    }
    load()
  }, [patternType])

  const typeIcons: Record<string, typeof TrendingUp> = {
    objection_risk: AlertTriangle,
    topic_risk: Target,
    rep_performance: TrendingUp,
    behavioral: Lightbulb,
  }

  return (
    <div className="p-8 animate-fade-in">
      {/* Header */}
      <div className="relative mb-8 bg-gradient-to-br from-emerald-600 via-emerald-700 to-green-800 rounded-2xl p-7 overflow-hidden shadow-lg shadow-emerald-900/20">
        <div className="relative">
          <div className="flex items-center gap-2.5 mb-2">
            <div className="w-2 h-2 rounded-full bg-emerald-300 animate-pulse" />
            <span className="text-xs font-semibold text-emerald-200 uppercase tracking-widest">Intelligence</span>
          </div>
          <h1 className="text-2xl font-bold text-white tracking-tight">Pattern Miner</h1>
          <p className="text-emerald-200 text-sm mt-1">Discover recurring patterns across all analyzed calls</p>
        </div>
      </div>

      {/* Summary stats */}
      {summary && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
          {[
            { label: 'Total Jobs', value: summary.total_jobs, icon: Layers },
            { label: 'Completed', value: summary.completed_jobs, icon: BarChart3 },
            { label: 'Segments', value: summary.total_segments, icon: TrendingUp },
            { label: 'Pattern Types', value: summary.available_patterns.length, icon: Filter },
          ].map(({ label, value, icon: Icon }) => (
            <div key={label} className="bg-white rounded-xl border border-slate-200 p-4 shadow-sm">
              <div className="flex items-center gap-2 mb-1"><Icon className="w-4 h-4 text-emerald-600" /><span className="text-xs text-slate-500 font-medium">{label}</span></div>
              <p className="text-xl font-bold text-slate-700">{value}</p>
            </div>
          ))}
        </div>
      )}

      {/* Pattern type selector */}
      <div className="flex items-center gap-3 mb-6">
        <Filter className="w-4 h-4 text-slate-400" />
        {['objection_risk', 'topic_risk', 'rep_performance', 'behavioral'].map(t => {
          const Icon = typeIcons[t] ?? TrendingUp
          return (
            <button
              key={t}
              onClick={() => setPatternType(t)}
              className={`flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded-lg transition ${patternType === t ? 'bg-emerald-600 text-white' : 'bg-slate-100 text-slate-600 hover:bg-slate-200'}`}
            >
              <Icon className="w-3.5 h-3.5" /> {t.replace(/_/g, ' ')}
            </button>
          )
        })}
      </div>

      {/* Patterns */}
      {loading ? (
        <p className="text-center py-16 text-slate-400 text-sm">Mining patterns…</p>
      ) : patterns.length === 0 ? (
        <div className="text-center py-16">
          <TrendingUp className="w-10 h-10 text-slate-300 mx-auto mb-3" />
          <p className="text-slate-500 text-sm">No patterns found. Process more calls to discover patterns.</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {patterns.map((p: any, i) => (
            <div key={i} className="bg-white rounded-xl border border-slate-200 p-5 shadow-sm hover:shadow-md transition">
              <div className="flex items-center gap-2 mb-3">
                {(() => { const Icon = typeIcons[patternType] ?? TrendingUp; return <Icon className="w-4 h-4 text-emerald-500" /> })()}
                <span className="text-sm font-bold text-slate-700">{p.name ?? p.label ?? `Pattern #${i + 1}`}</span>
                {p.score != null && (
                  <span className={`ml-auto px-2 py-0.5 rounded text-xs font-bold ${p.score > 0.7 ? 'bg-red-100 text-red-600' : p.score > 0.4 ? 'bg-amber-100 text-amber-600' : 'bg-emerald-100 text-emerald-600'}`}>
                    {(p.score * 100).toFixed(0)}%
                  </span>
                )}
              </div>
              {p.description && <p className="text-sm text-slate-500 mb-2">{p.description}</p>}
              {p.frequency != null && <p className="text-xs text-slate-400">Frequency: {p.frequency} occurrences</p>}
              {p.examples && (
                <details className="mt-2">
                  <summary className="text-xs text-indigo-500 cursor-pointer font-medium">View examples</summary>
                  <pre className="text-xs bg-slate-50 p-2 rounded mt-1 overflow-x-auto text-slate-600">{JSON.stringify(p.examples, null, 2)}</pre>
                </details>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
