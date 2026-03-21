import { useState } from 'react'
import { ChevronDown, ChevronUp, Clock } from 'lucide-react'
import { RiskBadge, Badge } from './Badge'
import type { SegmentPair } from '../api/client'

export function msToTimestamp(ms: number): string {
  const total = Math.floor(ms / 1000)
  const m = Math.floor(total / 60)
  const s = total % 60
  return `${m}:${s.toString().padStart(2, '0')}`
}

const riskStyles: Record<string, string> = {
  high: 'border-l-red-500 bg-red-50/40',
  medium: 'border-l-amber-400 bg-amber-50/40',
  low: 'border-l-emerald-500 bg-emerald-50/20',
}

export function SegmentCard({ pair }: { pair: SegmentPair }) {
  const [expanded, setExpanded] = useState(false)
  const { segment, extraction } = pair

  return (
    <div
      className={`border border-slate-200 border-l-4 ${riskStyles[extraction.risk] ?? 'border-l-slate-300 bg-white'} rounded-2xl p-4 shadow-sm hover:shadow-md transition-all duration-200`}
    >
      <div className="flex items-start justify-between gap-4">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap mb-2.5">
            <span className="inline-flex items-center gap-1 text-xs font-mono text-slate-500 bg-white border border-slate-200 px-2 py-0.5 rounded-md shadow-sm">
              <Clock className="w-3 h-3" />
              {msToTimestamp(segment.timestamp_ms)}
            </span>
            <span className="bg-indigo-50 text-indigo-700 border border-indigo-100 text-xs px-2.5 py-0.5 rounded-full font-semibold capitalize">
              {extraction.topic}
            </span>
            <span className="bg-slate-100 text-slate-600 border border-slate-200 text-xs px-2.5 py-0.5 rounded-full capitalize">
              {extraction.sentiment}
            </span>
            <RiskBadge risk={extraction.risk} />
            <span className="text-xs font-bold text-slate-400 ml-auto tabular-nums">
              {(extraction.risk_score * 100).toFixed(0)}%
            </span>
          </div>
          <p className="text-sm text-slate-700 leading-relaxed line-clamp-2">
            {segment.transcript || <em className="text-slate-400">No transcript</em>}
          </p>
        </div>

        <button
          onClick={() => setExpanded(!expanded)}
          className="text-slate-400 hover:text-slate-600 flex-shrink-0 p-1.5 rounded-lg hover:bg-white/80 transition-colors"
          aria-label={expanded ? 'Collapse' : 'Expand'}
        >
          {expanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
        </button>
      </div>

      {expanded && (
        <div className="mt-3 pt-3 border-t border-slate-200/60 space-y-3 animate-fade-in">
          {extraction.objections.length > 0 && (
            <div>
              <p className="text-xs font-bold text-red-600 mb-2 uppercase tracking-wider">
                Objections
              </p>
              <ul className="space-y-1">
                {extraction.objections.map((o, i) => (
                  <li key={i} className="text-xs text-slate-700 flex items-start gap-2 bg-red-50/60 rounded-lg px-3 py-1.5">
                    <span className="text-red-400 mt-0.5 flex-shrink-0">•</span>
                    {o}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {extraction.decision_signals.length > 0 && (
            <div>
              <p className="text-xs font-bold text-emerald-600 mb-2 uppercase tracking-wider">
                Decision Signals
              </p>
              <ul className="space-y-1">
                {extraction.decision_signals.map((s, i) => (
                  <li key={i} className="text-xs text-slate-700 flex items-start gap-2 bg-emerald-50/60 rounded-lg px-3 py-1.5">
                    <span className="text-emerald-400 mt-0.5 flex-shrink-0">•</span>
                    {s}
                  </li>
                ))}
              </ul>
            </div>
          )}

          <div className="flex items-center gap-5 text-xs text-slate-400 pt-2 border-t border-slate-100">
            <span>
              Confidence{' '}
              <span className="font-bold text-slate-600">
                {(extraction.confidence * 100).toFixed(0)}%
              </span>
            </span>
            <span>
              Model{' '}
              <span className="font-bold text-slate-600">{extraction.model_name}</span>
            </span>
            <span>
              Latency{' '}
              <span className="font-bold text-slate-600">{extraction.latency_ms}ms</span>
            </span>
          </div>
        </div>
      )}
    </div>
  )
}
