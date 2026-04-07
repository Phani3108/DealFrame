import { useState, useEffect, useCallback } from 'react'
import { MessageSquareText, Plus, Check, Trash2, Filter, Tag, Download } from 'lucide-react'
import { Badge } from '../components/Badge'
import {
  listAnnotations,
  createAnnotation,
  resolveAnnotation,
  deleteAnnotation,
  getAnnotationSummary,
  listJobs,
  type Annotation,
  type Job,
} from '../api/client'

export function Annotations() {
  const [annotations, setAnnotations] = useState<Annotation[]>([])
  const [jobs, setJobs] = useState<Job[]>([])
  const [selectedJob, setSelectedJob] = useState('')
  const [summary, setSummary] = useState<{ label_summary: Record<string, number>; total: number } | null>(null)
  const [loading, setLoading] = useState(true)
  const [showAdd, setShowAdd] = useState(false)
  const [newLabel, setNewLabel] = useState('objection')
  const [newComment, setNewComment] = useState('')

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const jobRes = await listJobs()
      const arr = Array.isArray(jobRes.jobs)
        ? jobRes.jobs
        : Object.entries(jobRes.jobs ?? {}).map(([id, v]: [string, any]) => ({ id, ...v }))
      setJobs(arr)

      const jid = selectedJob || (arr[0]?.job_id ?? '')
      if (!selectedJob && jid) setSelectedJob(jid)
      if (jid) {
        const [annRes, sumRes] = await Promise.all([
          listAnnotations(jid),
          getAnnotationSummary(jid),
        ])
        setAnnotations(annRes.annotations ?? [])
        setSummary(sumRes)
      }
    } catch { /* ignore */ }
    setLoading(false)
  }, [selectedJob])

  useEffect(() => { load() }, [load])

  const handleResolve = async (id: string) => {
    await resolveAnnotation(id)
    load()
  }

  const handleDelete = async (id: string) => {
    await deleteAnnotation(id)
    load()
  }

  const handleCreate = async () => {
    if (!selectedJob) return
    await createAnnotation({ job_id: selectedJob, segment_index: 0, start_word: 0, end_word: 5, label: newLabel, comment: newComment })
    setShowAdd(false)
    setNewComment('')
    load()
  }

  const labelColors: Record<string, string> = {
    objection: 'bg-red-500/15 text-red-400',
    intent: 'bg-blue-500/15 text-blue-400',
    decision: 'bg-emerald-500/15 text-emerald-400',
    risk: 'bg-amber-500/15 text-amber-400',
  }

  return (
    <div className="p-4 sm:p-6 lg:p-8 animate-fade-in">
      {/* Header */}
      <div className="relative mb-8 bg-gradient-to-br from-teal-600 via-teal-700 to-cyan-800 rounded-2xl p-7 overflow-hidden shadow-lg shadow-teal-900/20">
        <div className="relative flex items-start justify-between">
          <div>
            <div className="flex items-center gap-2.5 mb-2">
              <div className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
              <span className="text-xs font-semibold text-teal-200 uppercase tracking-widest">Annotations</span>
            </div>
            <h1 className="text-2xl font-bold text-white tracking-tight">Annotation Manager</h1>
            <p className="text-teal-200 text-sm mt-1">Label, comment, and resolve extraction annotations</p>
          </div>
          <button onClick={() => setShowAdd(true)} className="flex items-center gap-1.5 px-3.5 py-2 bg-white text-teal-700 text-sm font-bold rounded-xl hover:bg-teal-50 transition-all shadow-sm">
            <Plus className="w-3.5 h-3.5" /> Add Annotation
          </button>
        </div>
      </div>

      {/* Job selector + summary */}
      <div className="flex flex-wrap items-center gap-4 mb-6">
        <div className="flex items-center gap-2">
          <Filter className="w-4 h-4 text-slate-400" />
          <select
            value={selectedJob}
            onChange={e => setSelectedJob(e.target.value)}
            className="px-3 py-1.5 rounded-lg bg-white border border-slate-200 text-sm text-slate-700 shadow-sm"
          >
            {jobs.map(j => <option key={j.job_id} value={j.job_id}>{j.job_id.slice(0, 12)}… ({j.status})</option>)}
          </select>
        </div>
        {summary && (
          <div className="flex items-center gap-3 text-sm text-slate-500">
            <Tag className="w-4 h-4" />
            {Object.entries(summary.label_summary).map(([k, v]) => (
              <span key={k} className="px-2 py-0.5 rounded bg-slate-100 text-xs font-medium">{k}: {v}</span>
            ))}
            <span className="font-semibold text-slate-700">Total: {summary.total}</span>
          </div>
        )}
      </div>

      {/* Add form */}
      {showAdd && (
        <div className="mb-6 p-5 bg-white rounded-xl border border-slate-200 shadow-sm">
          <h3 className="font-semibold text-slate-700 mb-3">New Annotation</h3>
          <div className="flex gap-3 flex-wrap items-end">
            <div>
              <label className="text-xs text-slate-500 block mb-1">Label</label>
              <select value={newLabel} onChange={e => setNewLabel(e.target.value)} className="px-3 py-1.5 rounded-lg border border-slate-200 text-sm">
                <option value="objection">Objection</option>
                <option value="intent">Intent</option>
                <option value="decision">Decision</option>
                <option value="risk">Risk</option>
              </select>
            </div>
            <div className="flex-1">
              <label className="text-xs text-slate-500 block mb-1">Comment</label>
              <input value={newComment} onChange={e => setNewComment(e.target.value)} placeholder="Add a note…" className="w-full px-3 py-1.5 rounded-lg border border-slate-200 text-sm" />
            </div>
            <button onClick={handleCreate} className="px-4 py-1.5 bg-teal-600 text-white text-sm font-semibold rounded-lg hover:bg-teal-700 transition">Create</button>
            <button onClick={() => setShowAdd(false)} className="px-4 py-1.5 text-slate-500 text-sm rounded-lg hover:bg-slate-100 transition">Cancel</button>
          </div>
        </div>
      )}

      {/* List */}
      {loading ? (
        <div className="text-center py-16 text-slate-400 text-sm">Loading annotations…</div>
      ) : annotations.length === 0 ? (
        <div className="text-center py-16">
          <MessageSquareText className="w-10 h-10 text-slate-300 mx-auto mb-3" />
          <p className="text-slate-500 text-sm">No annotations yet. Add one above.</p>
        </div>
      ) : (
        <div className="space-y-2">
          {annotations.map(a => (
            <div key={a.id} className={`flex items-center gap-4 p-4 bg-white rounded-xl border shadow-sm transition ${a.resolved ? 'border-emerald-200 bg-emerald-50/30' : 'border-slate-200'}`}>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-1">
                  <span className={`inline-flex px-2 py-0.5 rounded text-xs font-bold ${labelColors[a.label] ?? 'bg-slate-100 text-slate-500'}`}>{a.label}</span>
                  {a.resolved && <Badge label="Resolved" />}
                  <span className="text-[11px] text-slate-400">seg #{a.segment_index} · words {a.start_word}-{a.end_word}</span>
                </div>
                {a.comment && <p className="text-sm text-slate-600 truncate">{a.comment}</p>}
              </div>
              <div className="flex items-center gap-1.5">
                {!a.resolved && (
                  <button onClick={() => handleResolve(a.id)} title="Resolve" className="p-1.5 rounded-lg hover:bg-emerald-50 text-emerald-500 transition">
                    <Check className="w-4 h-4" />
                  </button>
                )}
                <button onClick={() => handleDelete(a.id)} title="Delete" className="p-1.5 rounded-lg hover:bg-red-50 text-red-400 transition">
                  <Trash2 className="w-4 h-4" />
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
