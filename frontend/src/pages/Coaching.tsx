import { useState, useEffect } from 'react'
import { TrendingUp, TrendingDown, Minus, AlertTriangle, Target, Users, Loader2, RefreshCw } from 'lucide-react'

interface CoachingDimension {
  name: string
  score: number
  value: number
  benchmark: number
  verdict: 'excellent' | 'good' | 'needs_work'
  tip: string
}

interface CoachingCard {
  rep_id: string
  calls_analyzed: number
  overall_score: number
  grade: string
  dimensions: CoachingDimension[]
  strengths: string[]
  improvements: string[]
  example_moments: Array<{ job_id: string; timestamp: string; topic: string }>
}

function GradeBadge({ grade }: { grade: string }) {
  const colors: Record<string, string> = {
    A: 'bg-emerald-100 text-emerald-800',
    B: 'bg-blue-100 text-blue-800',
    C: 'bg-amber-100 text-amber-800',
    D: 'bg-red-100 text-red-800',
  }
  return (
    <span className={`text-3xl font-bold px-4 py-2 rounded-2xl ${colors[grade] ?? 'bg-slate-100 text-slate-800'}`}>
      {grade}
    </span>
  )
}

function ScoreBar({ score, verdict }: { score: number; verdict: string }) {
  const pct = Math.round(score * 100)
  const barColor = verdict === 'excellent' ? 'bg-emerald-500' : verdict === 'good' ? 'bg-blue-500' : 'bg-amber-500'
  return (
    <div className="flex items-center gap-3">
      <div className="flex-1 h-2 bg-slate-100 rounded-full overflow-hidden">
        <div className={`h-full rounded-full transition-all ${barColor}`} style={{ width: `${pct}%` }} />
      </div>
      <span className="text-sm font-medium text-slate-600 w-10 text-right">{pct}%</span>
    </div>
  )
}

export function Coaching() {
  const [repId, setRepId] = useState('')
  const [input, setInput] = useState('')
  const [card, setCard] = useState<CoachingCard | null>(null)
  const [reps, setReps] = useState<string[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    fetch('/api/v1/agents/coaching')
      .then(r => r.json())
      .then(d => setReps(d.reps ?? []))
      .catch(() => {})
  }, [])

  const loadCard = async (id: string) => {
    if (!id.trim()) return
    setLoading(true)
    setError(null)
    try {
      const res = await fetch(`/api/v1/agents/coaching/${encodeURIComponent(id)}`)
      if (!res.ok) {
        if (res.status === 404) throw new Error(`No data for rep "${id}". Make sure calls are recorded first.`)
        throw new Error(`HTTP ${res.status}`)
      }
      const data: CoachingCard = await res.json()
      setCard(data)
      setRepId(id)
    } catch (e: any) {
      setError(e.message)
      setCard(null)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="p-4 sm:p-6 max-w-4xl mx-auto">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-slate-900 flex items-center gap-2">
          <Target className="w-6 h-6 text-indigo-500" />
          Coaching Engine
        </h1>
        <p className="text-slate-500 mt-1 text-sm">Data-driven coaching cards benchmarked against top-quartile reps.</p>
      </div>

      {/* Rep selector */}
      <div className="flex gap-3 mb-6">
        <input
          className="flex-1 border border-slate-200 rounded-xl px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
          placeholder="Enter rep ID or name…"
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && loadCard(input)}
          list="reps-list"
        />
        <datalist id="reps-list">
          {reps.map(r => <option key={r} value={r} />)}
        </datalist>
        <button
          onClick={() => loadCard(input)}
          disabled={loading}
          className="px-5 py-2.5 bg-indigo-600 text-white rounded-xl text-sm font-medium hover:bg-indigo-700 disabled:opacity-40 flex items-center gap-2"
        >
          {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Users className="w-4 h-4" />}
          Load Card
        </button>
      </div>

      {/* Known reps shortcuts */}
      {reps.length > 0 && (
        <div className="flex flex-wrap gap-2 mb-6">
          {reps.map(r => (
            <button
              key={r}
              onClick={() => { setInput(r); loadCard(r) }}
              className="px-3 py-1 rounded-lg text-xs bg-slate-100 hover:bg-indigo-100 hover:text-indigo-700 text-slate-600 transition-colors"
            >
              {r}
            </button>
          ))}
        </div>
      )}

      {error && (
        <div className="bg-amber-50 border border-amber-200 rounded-xl p-4 text-sm text-amber-700 flex items-start gap-2 mb-6">
          <AlertTriangle className="w-4 h-4 mt-0.5 flex-shrink-0" />
          {error}
        </div>
      )}

      {card && (
        <div className="space-y-5">
          {/* Header */}
          <div className="bg-white rounded-2xl border border-slate-200 p-6 flex items-center justify-between">
            <div>
              <p className="text-sm text-slate-400 font-medium uppercase tracking-wide">Rep ID</p>
              <p className="text-xl font-bold text-slate-900">{card.rep_id}</p>
              <p className="text-sm text-slate-500 mt-1">{card.calls_analyzed} call{card.calls_analyzed !== 1 ? 's' : ''} analyzed</p>
            </div>
            <GradeBadge grade={card.grade} />
          </div>

          {/* Dimensions */}
          <div className="bg-white rounded-2xl border border-slate-200 p-6">
            <h3 className="font-semibold text-slate-800 mb-4">Performance Dimensions</h3>
            <div className="space-y-5">
              {card.dimensions.map(dim => (
                <div key={dim.name}>
                  <div className="flex items-center justify-between mb-1.5">
                    <span className="text-sm font-medium text-slate-700">{dim.name}</span>
                    <span className={`text-xs font-medium capitalize px-2 py-0.5 rounded-full ${
                      dim.verdict === 'excellent' ? 'bg-emerald-100 text-emerald-700' :
                      dim.verdict === 'good' ? 'bg-blue-100 text-blue-700' :
                      'bg-amber-100 text-amber-700'
                    }`}>{dim.verdict.replace('_', ' ')}</span>
                  </div>
                  <ScoreBar score={dim.score} verdict={dim.verdict} />
                  {dim.verdict === 'needs_work' && (
                    <p className="text-xs text-slate-500 mt-1.5 italic">{dim.tip}</p>
                  )}
                </div>
              ))}
            </div>
          </div>

          {/* Strengths + Improvements */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div className="bg-emerald-50 border border-emerald-200 rounded-2xl p-5">
              <h3 className="font-semibold text-emerald-800 mb-3 flex items-center gap-1.5">
                <TrendingUp className="w-4 h-4" /> Strengths
              </h3>
              <ul className="space-y-1.5">
                {card.strengths.map((s, i) => (
                  <li key={i} className="text-sm text-emerald-700 flex items-start gap-1.5">
                    <span className="text-emerald-400 mt-0.5">✓</span> {s}
                  </li>
                ))}
              </ul>
            </div>
            <div className="bg-amber-50 border border-amber-200 rounded-2xl p-5">
              <h3 className="font-semibold text-amber-800 mb-3 flex items-center gap-1.5">
                <TrendingDown className="w-4 h-4" /> Focus Areas
              </h3>
              <ul className="space-y-1.5">
                {card.improvements.map((imp, i) => (
                  <li key={i} className="text-sm text-amber-700 flex items-start gap-1.5">
                    <span className="text-amber-400 mt-0.5">→</span> {imp}
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
