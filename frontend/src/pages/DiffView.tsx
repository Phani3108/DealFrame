import { useState, useEffect } from 'react'
import { GitCompare, ArrowRight, Layers, AlertTriangle, ChevronDown } from 'lucide-react'
import { compareDiff, listComparableJobs } from '../api/client'

interface JobOption { job_id: string; status: string }

export function DiffView() {
  const [jobs, setJobs] = useState<JobOption[]>([])
  const [jobA, setJobA] = useState('')
  const [jobB, setJobB] = useState('')
  const [report, setReport] = useState<Record<string, unknown> | null>(null)
  const [loading, setLoading] = useState(false)
  const [jobsLoading, setJobsLoading] = useState(true)
  const [expandedKey, setExpandedKey] = useState<string | null>(null)

  useEffect(() => {
    listComparableJobs()
      .then(r => {
        setJobs(r.jobs ?? [])
        if (r.jobs?.length >= 2) {
          setJobA(r.jobs[0].job_id)
          setJobB(r.jobs[1].job_id)
        }
      })
      .catch(() => {})
      .finally(() => setJobsLoading(false))
  }, [])

  const runDiff = async () => {
    if (!jobA || !jobB || jobA === jobB) return
    setLoading(true)
    try {
      const res = await compareDiff(jobA, jobB)
      setReport(res.report)
    } catch { setReport(null) }
    setLoading(false)
  }

  const diffColor = (val: number) => {
    if (val > 0) return 'text-emerald-600'
    if (val < 0) return 'text-red-500'
    return 'text-slate-400'
  }

  return (
    <div className="p-8 animate-fade-in">
      {/* Header */}
      <div className="relative mb-8 bg-gradient-to-br from-pink-600 via-pink-700 to-rose-800 rounded-2xl p-7 overflow-hidden shadow-lg shadow-pink-900/20">
        <div className="relative">
          <div className="flex items-center gap-2.5 mb-2">
            <div className="w-2 h-2 rounded-full bg-pink-300 animate-pulse" />
            <span className="text-xs font-semibold text-pink-200 uppercase tracking-widest">Comparison</span>
          </div>
          <h1 className="text-2xl font-bold text-white tracking-tight">Diff Engine</h1>
          <p className="text-pink-200 text-sm mt-1">Compare extraction results across pipeline runs</p>
        </div>
      </div>

      {/* Job selectors */}
      <div className="flex flex-wrap items-center gap-4 mb-6">
        <div>
          <label className="block text-xs text-slate-500 font-medium mb-1">Job A</label>
          <select value={jobA} onChange={e => setJobA(e.target.value)} className="px-3 py-2 rounded-lg border border-slate-200 text-sm shadow-sm min-w-[180px]" disabled={jobsLoading}>
            {jobs.map(j => <option key={j.job_id} value={j.job_id}>{j.job_id.slice(0, 12)}… ({j.status})</option>)}
          </select>
        </div>
        <ArrowRight className="w-5 h-5 text-slate-300 mt-5" />
        <div>
          <label className="block text-xs text-slate-500 font-medium mb-1">Job B</label>
          <select value={jobB} onChange={e => setJobB(e.target.value)} className="px-3 py-2 rounded-lg border border-slate-200 text-sm shadow-sm min-w-[180px]" disabled={jobsLoading}>
            {jobs.map(j => <option key={j.job_id} value={j.job_id}>{j.job_id.slice(0, 12)}… ({j.status})</option>)}
          </select>
        </div>
        <button onClick={runDiff} disabled={loading || !jobA || !jobB || jobA === jobB} className="mt-5 flex items-center gap-1.5 px-5 py-2 bg-pink-600 text-white text-sm font-bold rounded-xl hover:bg-pink-700 disabled:opacity-40 transition shadow-sm">
          <GitCompare className="w-4 h-4" /> {loading ? 'Comparing…' : 'Compare'}
        </button>
      </div>

      {/* Report */}
      {report ? (
        <div className="space-y-3">
          {Object.entries(report).map(([key, val]) => {
            const isObj = typeof val === 'object' && val !== null
            return (
              <div key={key} className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
                <button
                  onClick={() => setExpandedKey(expandedKey === key ? null : key)}
                  className="w-full flex items-center justify-between px-5 py-4 text-left hover:bg-slate-50/50 transition"
                >
                  <div className="flex items-center gap-3">
                    <Layers className="w-4 h-4 text-slate-400" />
                    <span className="font-semibold text-slate-700 text-sm">{key}</span>
                  </div>
                  {isObj ? (
                    <ChevronDown className={`w-4 h-4 text-slate-400 transition-transform ${expandedKey === key ? 'rotate-180' : ''}`} />
                  ) : (
                    <span className={`font-mono text-sm font-bold ${typeof val === 'number' ? diffColor(val as number) : 'text-slate-600'}`}>
                      {String(val)}
                    </span>
                  )}
                </button>
                {isObj && expandedKey === key && (
                  <div className="px-5 pb-4 border-t border-slate-100">
                    <pre className="text-xs bg-slate-50 p-3 rounded-lg overflow-x-auto text-slate-600 mt-3">{JSON.stringify(val, null, 2)}</pre>
                  </div>
                )}
              </div>
            )
          })}
        </div>
      ) : !loading && (
        <div className="text-center py-16">
          <GitCompare className="w-10 h-10 text-slate-300 mx-auto mb-3" />
          <p className="text-slate-500 text-sm">Select two jobs above and click Compare to see the diff.</p>
        </div>
      )}
    </div>
  )
}
