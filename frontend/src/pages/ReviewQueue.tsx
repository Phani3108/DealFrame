import { useState, useEffect } from 'react'
import { CheckCircle2, XCircle, Edit3, BarChart3, Clock, AlertTriangle, ChevronDown } from 'lucide-react'
import { Badge } from '../components/Badge'
import {
  getReviewQueueFull,
  getALMetrics,
  approveReview,
  correctReview,
  rejectReview,
  type ReviewItem,
} from '../api/client'

export function ReviewQueue() {
  const [items, setItems] = useState<ReviewItem[]>([])
  const [metrics, setMetrics] = useState<{ total_items: number; status_counts: Record<string, number>; avg_confidence: number; threshold: number } | null>(null)
  const [filter, setFilter] = useState('')
  const [loading, setLoading] = useState(true)
  const [expandedId, setExpandedId] = useState<string | null>(null)
  const [correctionJson, setCorrectionJson] = useState('')

  const load = async () => {
    setLoading(true)
    try {
      const [qRes, mRes] = await Promise.all([
        getReviewQueueFull(filter || undefined),
        getALMetrics(),
      ])
      setItems(qRes.items ?? [])
      setMetrics(mRes)
    } catch { /* ignore */ }
    setLoading(false)
  }

  useEffect(() => { load() }, [filter])

  const handleApprove = async (id: string) => { await approveReview(id); load() }
  const handleReject = async (id: string) => { await rejectReview(id); load() }
  const handleCorrect = async (id: string) => {
    try {
      const parsed = JSON.parse(correctionJson)
      await correctReview(id, 'reviewer', parsed)
      setCorrectionJson('')
      setExpandedId(null)
      load()
    } catch { alert('Invalid JSON') }
  }

  const statusColors: Record<string, string> = {
    pending: 'bg-amber-100 text-amber-700',
    approved: 'bg-emerald-100 text-emerald-700',
    corrected: 'bg-blue-100 text-blue-700',
    rejected: 'bg-red-100 text-red-700',
  }

  return (
    <div className="p-8 animate-fade-in">
      {/* Header */}
      <div className="relative mb-8 bg-gradient-to-br from-amber-600 via-amber-700 to-orange-800 rounded-2xl p-7 overflow-hidden shadow-lg shadow-amber-900/20">
        <div className="relative">
          <div className="flex items-center gap-2.5 mb-2">
            <div className="w-2 h-2 rounded-full bg-amber-300 animate-pulse" />
            <span className="text-xs font-semibold text-amber-200 uppercase tracking-widest">Active Learning</span>
          </div>
          <h1 className="text-2xl font-bold text-white tracking-tight">Review Queue</h1>
          <p className="text-amber-200 text-sm mt-1">Human-in-the-loop extraction review & correction</p>
        </div>
      </div>

      {/* Metrics */}
      {metrics && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
          {[
            { label: 'Total Items', value: metrics.total_items, icon: BarChart3, color: 'text-slate-600' },
            { label: 'Pending', value: metrics.status_counts.pending ?? 0, icon: Clock, color: 'text-amber-600' },
            { label: 'Avg Confidence', value: `${(metrics.avg_confidence * 100).toFixed(1)}%`, icon: AlertTriangle, color: 'text-blue-600' },
            { label: 'Threshold', value: `${(metrics.threshold * 100).toFixed(0)}%`, icon: CheckCircle2, color: 'text-emerald-600' },
          ].map(({ label, value, icon: Icon, color }) => (
            <div key={label} className="bg-white rounded-xl border border-slate-200 p-4 shadow-sm">
              <div className="flex items-center gap-2 mb-1">
                <Icon className={`w-4 h-4 ${color}`} />
                <span className="text-xs text-slate-500 font-medium">{label}</span>
              </div>
              <p className={`text-xl font-bold ${color}`}>{value}</p>
            </div>
          ))}
        </div>
      )}

      {/* Filter */}
      <div className="flex items-center gap-3 mb-6">
        <span className="text-sm text-slate-500 font-medium">Status:</span>
        {['', 'pending', 'approved', 'corrected', 'rejected'].map(s => (
          <button
            key={s}
            onClick={() => setFilter(s)}
            className={`px-3 py-1 text-xs font-semibold rounded-lg transition ${filter === s ? 'bg-indigo-600 text-white' : 'bg-slate-100 text-slate-600 hover:bg-slate-200'}`}
          >
            {s || 'All'}
          </button>
        ))}
      </div>

      {/* Items */}
      {loading ? (
        <p className="text-center py-16 text-slate-400 text-sm">Loading queue…</p>
      ) : items.length === 0 ? (
        <div className="text-center py-16">
          <CheckCircle2 className="w-10 h-10 text-emerald-300 mx-auto mb-3" />
          <p className="text-slate-500 text-sm">Queue is empty — all caught up!</p>
        </div>
      ) : (
        <div className="space-y-2">
          {items.map(item => (
            <div key={item.id} className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
              <div className="flex items-center gap-4 p-4">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <span className={`px-2 py-0.5 rounded text-xs font-bold ${statusColors[item.status] ?? 'bg-slate-100 text-slate-500'}`}>{item.status}</span>
                    <span className="text-[11px] text-slate-400">Job {item.job_id.slice(0, 8)}… · Seg #{item.segment_index}</span>
                  </div>
                  <p className="text-sm text-slate-600">Confidence: <span className="font-semibold">{(item.confidence * 100).toFixed(1)}%</span></p>
                </div>
                <div className="flex items-center gap-1.5">
                  {item.status === 'pending' && (
                    <>
                      <button onClick={() => handleApprove(item.id)} title="Approve" className="p-2 rounded-lg hover:bg-emerald-50 text-emerald-500 transition">
                        <CheckCircle2 className="w-4 h-4" />
                      </button>
                      <button onClick={() => { setExpandedId(expandedId === item.id ? null : item.id); setCorrectionJson('') }} title="Correct" className="p-2 rounded-lg hover:bg-blue-50 text-blue-500 transition">
                        <Edit3 className="w-4 h-4" />
                      </button>
                      <button onClick={() => handleReject(item.id)} title="Reject" className="p-2 rounded-lg hover:bg-red-50 text-red-400 transition">
                        <XCircle className="w-4 h-4" />
                      </button>
                    </>
                  )}
                  <button onClick={() => setExpandedId(expandedId === item.id ? null : item.id)} className="p-2 rounded-lg hover:bg-slate-100 text-slate-400 transition">
                    <ChevronDown className={`w-4 h-4 transition-transform ${expandedId === item.id ? 'rotate-180' : ''}`} />
                  </button>
                </div>
              </div>

              {expandedId === item.id && (
                <div className="px-4 pb-4 border-t border-slate-100">
                  <p className="text-xs text-slate-500 mt-3 mb-1 font-medium">Extraction:</p>
                  <pre className="text-xs bg-slate-50 p-3 rounded-lg overflow-x-auto text-slate-600">{JSON.stringify(item.extraction, null, 2)}</pre>
                  {item.status === 'pending' && (
                    <div className="mt-3">
                      <p className="text-xs text-slate-500 mb-1 font-medium">Corrected JSON:</p>
                      <textarea
                        value={correctionJson}
                        onChange={e => setCorrectionJson(e.target.value)}
                        placeholder='{"topic": "pricing", "sentiment": "negative"}'
                        className="w-full px-3 py-2 rounded-lg border border-slate-200 text-xs font-mono h-20 resize-none"
                      />
                      <button onClick={() => handleCorrect(item.id)} className="mt-2 px-4 py-1.5 bg-blue-600 text-white text-xs font-semibold rounded-lg hover:bg-blue-700 transition">
                        Submit Correction
                      </button>
                    </div>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
