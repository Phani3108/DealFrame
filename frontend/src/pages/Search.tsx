import { useState } from 'react'
import { searchSegments, getWinLossPatterns, getObjectionVelocity, type SearchResultItem } from '../api/client'
import { Search as SearchIcon, AlertTriangle, TrendingUp, TrendingDown, Minus, Target, ChevronRight } from 'lucide-react'

const RISKS = ['', 'high', 'medium', 'low'] as const

function RiskPill({ risk }: { risk: string }) {
  const cls =
    risk === 'high' ? 'bg-red-50 text-red-700 border-red-200' :
    risk === 'medium' ? 'bg-amber-50 text-amber-700 border-amber-200' :
    'bg-emerald-50 text-emerald-700 border-emerald-200'
  return (
    <span className={`text-xs font-semibold px-2 py-0.5 rounded-full border ${cls}`}>
      {risk}
    </span>
  )
}

function TrendPill({ trend }: { trend: string }) {
  if (trend === 'rising') return (
    <span className="flex items-center gap-1 text-xs font-medium text-red-600">
      <TrendingUp className="w-3 h-3" /> Rising
    </span>
  )
  if (trend === 'falling') return (
    <span className="flex items-center gap-1 text-xs font-medium text-emerald-600">
      <TrendingDown className="w-3 h-3" /> Falling
    </span>
  )
  return (
    <span className="flex items-center gap-1 text-xs font-medium text-slate-500">
      <Minus className="w-3 h-3" /> Stable
    </span>
  )
}

function SearchResultCard({ result }: { result: SearchResultItem }) {
  const [expanded, setExpanded] = useState(false)
  return (
    <div className="bg-white rounded-xl border border-slate-200 overflow-hidden hover:shadow-sm transition-shadow">
      <button
        className="w-full text-left px-5 py-4"
        onClick={() => setExpanded(!expanded)}
      >
        <div className="flex items-start justify-between gap-3">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-1.5">
              <RiskPill risk={result.risk} />
              <span className="text-xs font-medium text-indigo-600 bg-indigo-50 px-2 py-0.5 rounded-full">
                {result.topic}
              </span>
              <span className="text-xs text-slate-400">{result.timestamp_str}</span>
              <span className="text-xs text-slate-400 ml-auto">score {result.score.toFixed(3)}</span>
            </div>
            <p className="text-sm text-slate-700 line-clamp-2">{result.transcript_snippet}</p>
          </div>
          <ChevronRight className={`w-4 h-4 text-slate-400 flex-shrink-0 transition-transform ${expanded ? 'rotate-90' : ''}`} />
        </div>
      </button>

      {expanded && (
        <div className="px-5 pb-4 border-t border-slate-100 pt-3">
          <div className="grid grid-cols-2 gap-4 text-xs">
            <div>
              <p className="text-slate-500 font-medium mb-1">Objections</p>
              {result.objections.length > 0
                ? result.objections.map((o, i) => (
                    <p key={i} className="text-slate-700 py-0.5">• {o}</p>
                  ))
                : <p className="text-slate-400">None</p>}
            </div>
            <div>
              <p className="text-slate-500 font-medium mb-1">Decision Signals</p>
              {result.decision_signals.length > 0
                ? result.decision_signals.map((s, i) => (
                    <p key={i} className="text-slate-700 py-0.5">• {s}</p>
                  ))
                : <p className="text-slate-400">None</p>}
            </div>
          </div>
          <p className="text-xs text-slate-400 mt-2">
            Video <code className="text-indigo-600">{result.video_id}</code> · Risk score {result.risk_score.toFixed(2)}
          </p>
        </div>
      )}
    </div>
  )
}

export function Search() {
  const [query, setQuery] = useState('')
  const [risk, setRisk] = useState<string>('')
  const [results, setResults] = useState<SearchResultItem[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(false)
  const [patterns, setPatterns] = useState<{ high_risk_objections: string[]; avg_risk_score: number } | null>(null)
  const [velocity, setVelocity] = useState<Array<{ objection: string; trend: string }>>([])
  const [insightsLoaded, setInsightsLoaded] = useState(false)

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!query.trim()) return
    setLoading(true)
    try {
      const res = await searchSegments(query, risk || undefined, undefined, 20)
      setResults(res.results)
      setTotal(res.total)
    } catch {
      setResults([])
      setTotal(0)
    } finally {
      setLoading(false)
    }
  }

  const loadInsights = async () => {
    if (insightsLoaded) return
    setInsightsLoaded(true)
    try {
      const [p, v] = await Promise.allSettled([getWinLossPatterns(), getObjectionVelocity()])
      if (p.status === 'fulfilled') setPatterns(p.value)
      if (v.status === 'fulfilled') setVelocity(v.value.items)
    } catch { /* empty */ }
  }

  return (
    <div className="p-8 max-w-5xl mx-auto">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-slate-900">Search</h1>
        <p className="text-slate-500 mt-1 text-sm">
          Full-text + filtered search across all processed video segments
        </p>
      </div>

      {/* Search form */}
      <form onSubmit={handleSearch} className="mb-6">
        <div className="flex gap-3">
          <div className="flex-1 relative">
            <SearchIcon className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
            <input
              type="text"
              placeholder='e.g. "pricing concern" or "competitor mention"'
              value={query}
              onChange={e => setQuery(e.target.value)}
              className="w-full pl-10 pr-4 py-3 border border-slate-200 rounded-xl text-sm bg-white shadow-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent placeholder:text-slate-400"
            />
          </div>
          <select
            value={risk}
            onChange={e => setRisk(e.target.value)}
            className="px-3 py-3 border border-slate-200 rounded-xl text-sm bg-white shadow-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 text-slate-700"
          >
            {RISKS.map(r => (
              <option key={r} value={r}>{r ? `Risk: ${r}` : 'All risks'}</option>
            ))}
          </select>
          <button
            type="submit"
            disabled={loading}
            className="px-6 py-3 bg-indigo-600 text-white rounded-xl text-sm font-semibold hover:bg-indigo-700 disabled:opacity-50 transition-colors shadow-sm"
          >
            {loading ? 'Searching…' : 'Search'}
          </button>
        </div>
      </form>

      {/* Results */}
      {results.length > 0 && (
        <div className="mb-8">
          <p className="text-sm text-slate-500 mb-3">
            {total} result{total !== 1 ? 's' : ''} for <span className="font-medium text-slate-800">"{query}"</span>
          </p>
          <div className="space-y-3">
            {results.map(r => <SearchResultCard key={r.doc_id} result={r} />)}
          </div>
        </div>
      )}

      {results.length === 0 && !loading && query && (
        <div className="text-center py-12 text-slate-400">
          <SearchIcon className="w-10 h-10 mx-auto mb-3 opacity-30" />
          <p className="text-sm">No results for "{query}" — try different keywords</p>
          <p className="text-xs mt-1">Index will populate as videos are processed</p>
        </div>
      )}

      {!query && (
        <div className="text-center py-12 text-slate-400">
          <SearchIcon className="w-10 h-10 mx-auto mb-3 opacity-30" />
          <p className="text-sm">Enter keywords to search across all video segments</p>
          <p className="text-xs mt-1">Searches transcripts, objections, topics, and decision signals</p>
        </div>
      )}

      {/* Portfolio Insights */}
      <div className="border-t border-slate-200 pt-8">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-base font-semibold text-slate-900">Portfolio Insights</h2>
          {!insightsLoaded && (
            <button
              onClick={loadInsights}
              className="flex items-center gap-1.5 text-sm text-indigo-600 hover:text-indigo-800 font-medium"
            >
              <Target className="w-3.5 h-3.5" />
              Load Insights
            </button>
          )}
        </div>

        {insightsLoaded && (
          <div className="grid grid-cols-2 gap-6">
            {/* Win/Loss patterns */}
            <div className="bg-white rounded-xl border border-slate-200 p-5">
              <h3 className="text-sm font-semibold text-slate-900 mb-3">Top Risk Objections</h3>
              {patterns?.high_risk_objections && patterns.high_risk_objections.length > 0 ? (
                <div className="space-y-2">
                  {patterns.high_risk_objections.map((o, i) => (
                    <div key={i} className="flex items-center gap-2">
                      <AlertTriangle className="w-3.5 h-3.5 text-red-500 flex-shrink-0" />
                      <span className="text-sm text-slate-700 truncate">{o}</span>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-sm text-slate-400">No data yet — process some videos first</p>
              )}
              {patterns && (
                <p className="text-xs text-slate-400 mt-3 pt-3 border-t border-slate-100">
                  Avg risk score: {patterns.avg_risk_score.toFixed(2)}
                </p>
              )}
            </div>

            {/* Objection velocity */}
            <div className="bg-white rounded-xl border border-slate-200 p-5">
              <h3 className="text-sm font-semibold text-slate-900 mb-3">Objection Velocity</h3>
              {velocity.length > 0 ? (
                <div className="space-y-2">
                  {velocity.slice(0, 5).map((v, i) => (
                    <div key={i} className="flex items-center justify-between">
                      <span className="text-sm text-slate-700 truncate max-w-[180px]">{v.objection}</span>
                      <TrendPill trend={v.trend} />
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-sm text-slate-400">No trend data yet</p>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
