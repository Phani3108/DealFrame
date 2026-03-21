import { useState, useEffect, useRef } from 'react'
import {
  Layers, Play, X, CheckCircle2, XCircle, Clock, Loader2,
  AlertCircle, ChevronRight, Plus, Trash2,
} from 'lucide-react'

const VERTICALS = ['', 'sales', 'ux_research', 'customer_success', 'real_estate']

interface BatchItem {
  item_id: string
  url: string
  status: 'pending' | 'running' | 'completed' | 'failed'
  job_id?: string
  error?: string
}

interface BatchJob {
  batch_id: string
  status: string
  progress_pct: number
  total: number
  completed_count: number
  failed_count: number
  vertical?: string
  items: BatchItem[]
  priority: number
}

function StatusIcon({ status }: { status: string }) {
  if (status === 'completed') return <CheckCircle2 className="w-4 h-4 text-emerald-500" />
  if (status === 'failed') return <XCircle className="w-4 h-4 text-red-400" />
  if (status === 'running') return <Loader2 className="w-4 h-4 text-indigo-500 animate-spin" />
  return <Clock className="w-4 h-4 text-slate-300" />
}

function ProgressBar({ value, total }: { value: number; total: number }) {
  const pct = total > 0 ? (value / total) * 100 : 0
  return (
    <div className="w-full bg-slate-100 rounded-full h-2">
      <div
        className="h-2 rounded-full bg-indigo-500 transition-all duration-500"
        style={{ width: `${pct}%` }}
      />
    </div>
  )
}

export function Batch() {
  const [urlsText, setUrlsText] = useState('')
  const [vertical, setVertical] = useState('')
  const [schemaId, setSchemaId] = useState('')
  const [priority, setPriority] = useState(5)
  const [schemas, setSchemas] = useState<{ schema_id: string; name: string }[]>([])
  const [submitting, setSubmitting] = useState(false)
  const [batches, setBatches] = useState<BatchJob[]>([])
  const [expanded, setExpanded] = useState<string | null>(null)
  const pollRefs = useRef<Record<string, ReturnType<typeof setInterval>>>({})

  useEffect(() => {
    Promise.all([
      fetch('/api/v1/schemas').then(r => r.json()).catch(() => ({ schemas: [] })),
      fetch('/api/v1/batch').then(r => r.json()).catch(() => ({ batches: [] })),
    ]).then(([s, b]) => {
      setSchemas(s.schemas ?? [])
      setBatches(b.batches ?? [])
    })
    return () => Object.values(pollRefs.current).forEach(clearInterval)
  }, [])

  const startPolling = (batchId: string) => {
    if (pollRefs.current[batchId]) return
    const id = setInterval(async () => {
      const r = await fetch(`/api/v1/batch/${batchId}`)
      if (!r.ok) return
      const data = await r.json()
      const job: BatchJob = data.batch
      setBatches(prev => prev.map(b => b.batch_id === batchId ? job : b))
      if (job.status !== 'running' && job.status !== 'pending') {
        clearInterval(pollRefs.current[batchId])
        delete pollRefs.current[batchId]
      }
    }, 3000)
    pollRefs.current[batchId] = id
  }

  const submit = async () => {
    const urls = urlsText.split('\n').map(s => s.trim()).filter(Boolean)
    if (!urls.length) return
    setSubmitting(true)
    try {
      const body: Record<string, unknown> = { urls, priority }
      if (vertical) body.vertical = vertical
      if (schemaId) body.schema_id = schemaId
      const r = await fetch('/api/v1/batch', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })
      const d = await r.json()
      const newBatch: BatchJob = d.batch
      setBatches(prev => [newBatch, ...prev])
      setUrlsText('')
      if (newBatch.status === 'running' || newBatch.status === 'pending') {
        startPolling(newBatch.batch_id)
      }
    } finally {
      setSubmitting(false)
    }
  }

  const cancelBatch = async (batchId: string) => {
    await fetch(`/api/v1/batch/${batchId}/cancel`, { method: 'DELETE' })
    setBatches(prev => prev.map(b =>
      b.batch_id === batchId ? { ...b, status: 'failed' } : b
    ))
  }

  return (
    <div className="p-6 max-w-3xl mx-auto space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-slate-900 flex items-center gap-2">
          <Layers className="w-6 h-6 text-indigo-500" />
          Batch Processing
        </h1>
        <p className="text-slate-500 mt-1 text-sm">Process multiple video URLs in parallel.</p>
      </div>

      {/* Submit form */}
      <div className="bg-white rounded-2xl border border-slate-200 p-5 space-y-4">
        <h2 className="font-semibold text-slate-800 text-sm">New Batch</h2>
        <textarea
          className="w-full border border-slate-200 rounded-xl px-4 py-3 text-sm font-mono resize-none"
          rows={5}
          placeholder={`https://example.com/call1.mp4\nhttps://example.com/call2.mp4\nhttps://example.com/call3.mp4`}
          value={urlsText}
          onChange={e => setUrlsText(e.target.value)}
        />

        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="text-xs text-slate-500 mb-1 block">Vertical</label>
            <select
              className="w-full border border-slate-200 rounded-xl px-3 py-2.5 text-sm bg-white"
              value={vertical}
              onChange={e => setVertical(e.target.value)}
            >
              <option value="">— Default —</option>
              {VERTICALS.filter(Boolean).map(v => (
                <option key={v} value={v}>{v.replace('_', ' ')}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="text-xs text-slate-500 mb-1 block">Schema</label>
            <select
              className="w-full border border-slate-200 rounded-xl px-3 py-2.5 text-sm bg-white"
              value={schemaId}
              onChange={e => setSchemaId(e.target.value)}
            >
              <option value="">— Default —</option>
              {schemas.map(s => (
                <option key={s.schema_id} value={s.schema_id}>{s.name}</option>
              ))}
            </select>
          </div>
        </div>

        <div>
          <label className="text-xs text-slate-500 mb-1 block">Priority: {priority}</label>
          <input
            type="range"
            min={1}
            max={10}
            value={priority}
            onChange={e => setPriority(Number(e.target.value))}
            className="w-full accent-indigo-600"
          />
          <div className="flex justify-between text-xs text-slate-400 mt-0.5">
            <span>Lower</span><span>Higher</span>
          </div>
        </div>

        <button
          onClick={submit}
          disabled={submitting || !urlsText.trim()}
          className="w-full flex items-center justify-center gap-2 py-2.5 bg-indigo-600 text-white text-sm font-medium rounded-xl hover:bg-indigo-700 disabled:opacity-40"
        >
          {submitting
            ? <Loader2 className="w-4 h-4 animate-spin" />
            : <Play className="w-4 h-4" />}
          Submit Batch
        </button>
      </div>

      {/* Past batches */}
      {batches.length > 0 && (
        <div>
          <h2 className="font-semibold text-slate-800 mb-3">Batches</h2>
          <div className="space-y-3">
            {batches.map(batch => (
              <div key={batch.batch_id} className="bg-white rounded-2xl border border-slate-200 overflow-hidden">
                <div
                  className="flex items-center gap-3 px-5 py-4 cursor-pointer"
                  onClick={() => setExpanded(prev => prev === batch.batch_id ? null : batch.batch_id)}
                >
                  <StatusIcon status={batch.status} />
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-slate-800 truncate font-mono">{batch.batch_id}</p>
                    <div className="mt-1 flex items-center gap-3">
                      <ProgressBar value={batch.completed_count} total={batch.total} />
                      <span className="text-xs text-slate-500 whitespace-nowrap">
                        {batch.completed_count}/{batch.total}
                        {batch.failed_count > 0 && <span className="text-red-400"> · {batch.failed_count} failed</span>}
                      </span>
                    </div>
                  </div>
                  {batch.vertical && (
                    <span className="text-xs px-2 py-0.5 bg-indigo-50 text-indigo-600 rounded-full">{batch.vertical}</span>
                  )}
                  {(batch.status === 'pending' || batch.status === 'running') && (
                    <button
                      onClick={e => { e.stopPropagation(); cancelBatch(batch.batch_id) }}
                      className="text-red-400 hover:text-red-600"
                    >
                      <X className="w-4 h-4" />
                    </button>
                  )}
                  <ChevronRight className={`w-4 h-4 text-slate-400 transition-transform ${expanded === batch.batch_id ? 'rotate-90' : ''}`} />
                </div>
                {expanded === batch.batch_id && batch.items?.length > 0 && (
                  <div className="border-t border-slate-100 px-5 py-3 space-y-2 bg-slate-50">
                    {batch.items.map(item => (
                      <div key={item.item_id} className="flex items-start gap-2 text-xs">
                        <StatusIcon status={item.status} />
                        <span className="font-mono text-slate-600 flex-1 truncate">{item.url}</span>
                        {item.error && <span className="text-red-400">{item.error}</span>}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
