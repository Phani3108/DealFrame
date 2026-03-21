import { useState } from 'react'
import {
  Calendar, Loader2, AlertTriangle, TrendingUp, TrendingDown,
  Minus, ChevronDown, ChevronUp, MessageSquare, CheckSquare,
} from 'lucide-react'

interface MeetingBrief {
  company: string
  contact: string | null
  prior_calls: number
  open_objections: string[]
  recurring_topics: Record<string, number>
  open_action_items: string[]
  risk_trajectory: 'rising' | 'falling' | 'stable' | 'new'
  last_risk_score: number
  talking_points: string[]
  watch_outs: string[]
  raw_excerpts: string[]
}

function RiskTrajectoryBadge({ trajectory, score }: { trajectory: string; score: number }) {
  const map = {
    rising:  { icon: TrendingUp,   cls: 'bg-red-50 text-red-600',       label: 'Rising Risk' },
    falling: { icon: TrendingDown, cls: 'bg-emerald-50 text-emerald-600', label: 'Falling Risk' },
    stable:  { icon: Minus,        cls: 'bg-slate-100 text-slate-600',   label: 'Stable' },
    new:     { icon: Calendar,     cls: 'bg-blue-50 text-blue-600',      label: 'New Contact' },
  } as const
  const t = map[trajectory as keyof typeof map] ?? map.stable
  const Icon = t.icon
  return (
    <span className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-sm font-medium ${t.cls}`}>
      <Icon className="w-4 h-4" />
      {t.label} · {(score * 100).toFixed(0)}%
    </span>
  )
}

function Accordion({ title, count, children }: { title: string; count: number; children: React.ReactNode }) {
  const [open, setOpen] = useState(true)
  return (
    <div className="bg-white rounded-2xl border border-slate-200 overflow-hidden">
      <button
        onClick={() => setOpen(o => !o)}
        className="w-full flex items-center justify-between px-5 py-4 text-left"
      >
        <span className="font-semibold text-slate-800 text-sm">
          {title} <span className="text-slate-400 font-normal">({count})</span>
        </span>
        {open ? <ChevronUp className="w-4 h-4 text-slate-400" /> : <ChevronDown className="w-4 h-4 text-slate-400" />}
      </button>
      {open && <div className="border-t border-slate-100 px-5 py-4">{children}</div>}
    </div>
  )
}

export function MeetingPrep() {
  const [company, setCompany] = useState('')
  const [contact, setContact] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [brief, setBrief] = useState<MeetingBrief | null>(null)

  const generate = async () => {
    if (!company.trim()) { setError('Company is required'); return }
    setError(''); setLoading(true); setBrief(null)
    try {
      const r = await fetch('/api/v1/agents/meeting-prep', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ company: company.trim(), contact: contact.trim() || undefined }),
      })
      const d = await r.json()
      if (!r.ok) {
        setError(d.detail ?? 'Failed to generate brief')
      } else {
        setBrief(d.brief)
      }
    } catch (e) {
      setError(String(e))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="p-6 max-w-3xl mx-auto space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-900 flex items-center gap-2">
          <Calendar className="w-6 h-6 text-indigo-500" />
          Meeting Prep
        </h1>
        <p className="text-slate-500 mt-1 text-sm">Generate a brief from historical call intelligence before your next meeting.</p>
      </div>

      {/* Input */}
      <div className="bg-white rounded-2xl border border-slate-200 p-5 space-y-3">
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="text-xs text-slate-500 mb-1 block">Company *</label>
            <input
              className="w-full border border-slate-200 rounded-xl px-4 py-2.5 text-sm"
              placeholder="Acme Corp"
              value={company}
              onChange={e => setCompany(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && generate()}
            />
          </div>
          <div>
            <label className="text-xs text-slate-500 mb-1 block">Contact (optional)</label>
            <input
              className="w-full border border-slate-200 rounded-xl px-4 py-2.5 text-sm"
              placeholder="Jane Smith"
              value={contact}
              onChange={e => setContact(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && generate()}
            />
          </div>
        </div>
        {error && (
          <p className="text-sm text-red-500 flex items-center gap-1.5">
            <AlertTriangle className="w-4 h-4" />{error}
          </p>
        )}
        <button
          onClick={generate}
          disabled={loading || !company.trim()}
          className="w-full flex items-center justify-center gap-2 py-2.5 bg-indigo-600 text-white text-sm font-medium rounded-xl hover:bg-indigo-700 disabled:opacity-40"
        >
          {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Calendar className="w-4 h-4" />}
          Generate Brief
        </button>
      </div>

      {/* Result */}
      {brief && (
        <div className="space-y-4">
          {/* Header */}
          <div className="bg-white rounded-2xl border border-slate-200 p-5">
            <div className="flex items-start justify-between gap-4">
              <div>
                <h2 className="text-lg font-bold text-slate-900">{brief.company}</h2>
                {brief.contact && <p className="text-sm text-slate-500">{brief.contact}</p>}
                <p className="text-xs text-slate-400 mt-0.5">{brief.prior_calls} prior call{brief.prior_calls !== 1 ? 's' : ''} analyzed</p>
              </div>
              <RiskTrajectoryBadge trajectory={brief.risk_trajectory} score={brief.last_risk_score} />
            </div>
          </div>

          {/* Talking Points */}
          {brief.talking_points.length > 0 && (
            <Accordion title="Talking Points" count={brief.talking_points.length}>
              <ul className="space-y-2">
                {brief.talking_points.map((pt, i) => (
                  <li key={i} className="flex items-start gap-2 text-sm text-slate-700">
                    <span className="text-indigo-400 font-bold mt-0.5">↗</span>
                    {pt}
                  </li>
                ))}
              </ul>
            </Accordion>
          )}

          {/* Watch-outs */}
          {brief.watch_outs.length > 0 && (
            <Accordion title="Watch-outs" count={brief.watch_outs.length}>
              <ul className="space-y-2">
                {brief.watch_outs.map((w, i) => (
                  <li key={i} className="flex items-start gap-2 text-sm text-slate-700">
                    <AlertTriangle className="w-4 h-4 text-amber-400 mt-0.5 shrink-0" />
                    {w}
                  </li>
                ))}
              </ul>
            </Accordion>
          )}

          {/* Open Objections */}
          {brief.open_objections.length > 0 && (
            <Accordion title="Open Objections" count={brief.open_objections.length}>
              <ul className="space-y-2">
                {brief.open_objections.map((o, i) => (
                  <li key={i} className="flex items-start gap-2 text-sm text-slate-700">
                    <MessageSquare className="w-4 h-4 text-red-400 mt-0.5 shrink-0" />
                    {o}
                  </li>
                ))}
              </ul>
            </Accordion>
          )}

          {/* Action Items */}
          {brief.open_action_items.length > 0 && (
            <Accordion title="Action Items" count={brief.open_action_items.length}>
              <ul className="space-y-2">
                {brief.open_action_items.map((a, i) => (
                  <li key={i} className="flex items-start gap-2 text-sm text-slate-700">
                    <CheckSquare className="w-4 h-4 text-emerald-400 mt-0.5 shrink-0" />
                    {a}
                  </li>
                ))}
              </ul>
            </Accordion>
          )}

          {/* Recurring Topics */}
          {Object.keys(brief.recurring_topics).length > 0 && (
            <Accordion title="Recurring Topics" count={Object.keys(brief.recurring_topics).length}>
              <div className="flex flex-wrap gap-2">
                {Object.entries(brief.recurring_topics)
                  .sort(([, a], [, b]) => b - a)
                  .map(([topic, count]) => (
                    <span key={topic} className="px-3 py-1 bg-indigo-50 text-indigo-700 rounded-full text-xs font-medium">
                      {topic} × {count}
                    </span>
                  ))}
              </div>
            </Accordion>
          )}

          {/* Raw Excerpts */}
          {brief.raw_excerpts.length > 0 && (
            <Accordion title="Excerpts" count={brief.raw_excerpts.length}>
              <div className="space-y-2">
                {brief.raw_excerpts.map((ex, i) => (
                  <blockquote key={i} className="border-l-4 border-slate-200 pl-3 text-sm text-slate-600 italic">
                    "{ex}"
                  </blockquote>
                ))}
              </div>
            </Accordion>
          )}
        </div>
      )}
    </div>
  )
}
