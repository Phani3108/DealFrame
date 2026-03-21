import { useState, useEffect } from 'react'
import { useParams, Link } from 'react-router-dom'
import { ArrowLeft, Clock, FileVideo, AlertTriangle, TrendingUp, Loader2 } from 'lucide-react'
import { SegmentCard } from '../components/SegmentCard'
import { getJob, getSpeakers, createSummary, listClips, extractSignificantClips, type Job } from '../api/client'

type Tab = 'segments' | 'summary' | 'clips' | 'speakers'
const SUMMARY_TYPES = ['executive', 'action_items', 'meeting_notes', 'deal_brief']

function RiskMeter({ score }: { score: number }) {
  const pct = Math.round(score * 100)
  const color = score > 0.6 ? 'bg-red-500' : score > 0.3 ? 'bg-amber-400' : 'bg-emerald-500'
  const textColor = score > 0.6 ? 'text-red-600' : score > 0.3 ? 'text-amber-600' : 'text-emerald-600'
  return (
    <div className="text-right">
      <p className="text-xs text-slate-500 mb-1">Overall risk</p>
      <p className={`text-3xl font-bold tabular-nums ${textColor}`}>{pct}%</p>
      <div className="w-24 h-1.5 bg-slate-100 rounded-full mt-1.5 ml-auto overflow-hidden">
        <div className={`h-full ${color} rounded-full`} style={{ width: `${pct}%` }} />
      </div>
    </div>
  )
}

export function Results() {
  const { jobId } = useParams<{ jobId: string }>()
  const [job, setJob] = useState<Job | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [tab, setTab] = useState<Tab>('segments')

  // Summary
  const [summaryType, setSummaryType] = useState('executive')
  const [summaryContent, setSummaryContent] = useState('')
  const [summaryLoading, setSummaryLoading] = useState(false)

  // Clips
  const [clips, setClips] = useState<Array<{ filename: string; segment_index: number; url: string }>>([])
  const [clipsLoading, setClipsLoading] = useState(false)
  const [sigLoading, setSigLoading] = useState(false)

  // Speakers
  const [speakers, setSpeakers] = useState<Array<{ speaker: string; turns: number; words: number; percentage: number }>>([])
  const [speakersLoading, setSpeakersLoading] = useState(false)

  useEffect(() => {
    if (!jobId) return
    getJob(jobId)
      .then(setJob)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }, [jobId])

  const loadSummary = async () => {
    if (!jobId) return
    setSummaryLoading(true)
    try {
      const d = await createSummary(jobId, summaryType)
      setSummaryContent(d.content)
    } catch { /* ignore */ }
    finally { setSummaryLoading(false) }
  }

  const loadClips = async () => {
    if (!jobId) return
    setClipsLoading(true)
    try {
      const d = await listClips(jobId)
      setClips(d.clips ?? [])
    } catch { /* ignore */ }
    finally { setClipsLoading(false) }
  }

  const loadSpeakers = async () => {
    if (!jobId) return
    setSpeakersLoading(true)
    try {
      const d = await getSpeakers(jobId)
      setSpeakers(d.speakers ?? [])
    } catch { /* ignore */ }
    finally { setSpeakersLoading(false) }
  }

  const extractSig = async () => {
    if (!jobId) return
    setSigLoading(true)
    try {
      const d = await extractSignificantClips(jobId, 3)
      // reload clips after extraction
      const d2 = await listClips(jobId)
      setClips(d2.clips ?? [])
    } catch { /* ignore */ }
    finally { setSigLoading(false) }
  }

  const onTabChange = (t: Tab) => {
    setTab(t)
    if (t === 'summary' && !summaryContent) loadSummary()
    if (t === 'clips' && clips.length === 0) loadClips()
    if (t === 'speakers' && speakers.length === 0) loadSpeakers()
  }

  if (loading) {
    return (
      <div className="p-8 flex items-center gap-3 text-slate-400">
        <div className="w-4 h-4 border-2 border-slate-300 border-t-indigo-500 rounded-full animate-spin" />
        Loading results…
      </div>
    )
  }

  if (error || !job) {
    return (
      <div className="p-8">
        <Link to="/" className="inline-flex items-center gap-1.5 text-sm text-slate-500 hover:text-slate-700 mb-4">
          <ArrowLeft className="w-4 h-4" /> Back
        </Link>
        <div className="card p-8 text-center">
          <AlertTriangle className="w-8 h-8 text-red-400 mx-auto mb-2" />
          <p className="text-slate-600">{error || 'Job not found'}</p>
        </div>
      </div>
    )
  }

  const intel = job.result
  const segments = intel?.segments ?? []
  const highRiskCount = segments.filter(p => p.extraction.risk === 'high').length

  return (
    <div className="p-8 max-w-4xl animate-fade-in">
      {/* Back */}
      <Link to="/" className="inline-flex items-center gap-1.5 text-sm text-slate-500 hover:text-slate-700 mb-6 group">
        <ArrowLeft className="w-4 h-4 group-hover:-translate-x-0.5 transition-transform" />
        Dashboard
      </Link>

      {/* Header card */}
      <div className="card p-6 mb-6">
        <div className="flex items-start justify-between">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <FileVideo className="w-5 h-5 text-indigo-500" />
              <h1 className="text-lg font-bold text-slate-900">Analysis Results</h1>
            </div>
            <div className="flex items-center gap-4 text-sm text-slate-500 font-mono">
              <span>{jobId}</span>
              {intel && (
                <span className="flex items-center gap-1 font-sans">
                  <Clock className="w-3.5 h-3.5" />
                  {Math.round((intel.duration_ms ?? 0) / 1000)}s
                </span>
              )}
            </div>
          </div>
          <div className="flex items-center gap-6">
            {highRiskCount > 0 && (
              <div className="text-right">
                <p className="text-xs text-slate-500">High risk segments</p>
                <p className="text-3xl font-bold text-red-600 tabular-nums">{highRiskCount}</p>
              </div>
            )}
            {intel?.overall_risk_score != null && (
              <RiskMeter score={intel.overall_risk_score} />
            )}
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 bg-slate-100 rounded-xl p-1 mb-6">
        {(['segments', 'summary', 'clips', 'speakers'] as Tab[]).map(t => (
          <button
            key={t}
            onClick={() => onTabChange(t)}
            className={`flex-1 py-2 text-sm font-medium rounded-lg transition-all ${
              tab === t ? 'bg-white shadow text-slate-900' : 'text-slate-500 hover:text-slate-700'
            }`}
          >
            {t.charAt(0).toUpperCase() + t.slice(1)}
          </button>
        ))}
      </div>

      {/* Status */}
      {job.status !== 'completed' ? (
        <div className="card p-10 text-center">
          <p className="text-slate-500">
            Status: <span className="font-semibold text-slate-800 capitalize">{job.status}</span>
          </p>
          {job.status === 'failed' && job.error && (
            <p className="text-sm text-red-600 mt-2">{job.error}</p>
          )}
        </div>
      ) : tab === 'segments' ? (
        segments.length === 0 ? (
          <div className="card p-10 text-center">
            <TrendingUp className="w-8 h-8 text-slate-300 mx-auto mb-2" />
            <p className="text-slate-400 text-sm">No segments found in this video.</p>
          </div>
        ) : (
          <>
            <div className="flex items-center gap-6 mb-4 text-sm text-slate-500">
              <span>{segments.length} segment{segments.length !== 1 ? 's' : ''} analyzed</span>
              {highRiskCount > 0 && (
                <span className="flex items-center gap-1 text-red-600 font-medium">
                  <AlertTriangle className="w-3.5 h-3.5" />
                  {highRiskCount} high risk
                </span>
              )}
              <span className="ml-auto">Scroll to explore</span>
            </div>
            <div className="space-y-3">
              {segments.map((pair, i) => (
                <SegmentCard key={i} pair={pair} />
              ))}
            </div>
          </>
        )
      ) : tab === 'summary' ? (
        <div className="space-y-4">
          <div className="flex items-center gap-3">
            <select
              className="border border-slate-200 rounded-xl px-3 py-2 text-sm bg-white"
              value={summaryType}
              onChange={e => { setSummaryType(e.target.value); setSummaryContent('') }}
            >
              {SUMMARY_TYPES.map(t => <option key={t} value={t}>{t.replace('_', ' ')}</option>)}
            </select>
            <button
              onClick={loadSummary}
              disabled={summaryLoading}
              className="px-4 py-2 bg-indigo-600 text-white text-sm rounded-xl hover:bg-indigo-700 disabled:opacity-40 flex items-center gap-2"
            >
              {summaryLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Generate'}
            </button>
          </div>
          {summaryContent && (
            <div className="bg-white rounded-2xl border border-slate-200 p-6">
              <pre className="whitespace-pre-wrap text-sm text-slate-700 font-sans leading-relaxed">{summaryContent}</pre>
            </div>
          )}
        </div>
      ) : tab === 'clips' ? (
        <div className="space-y-4">
          <div className="flex gap-3">
            <button
              onClick={loadClips}
              disabled={clipsLoading}
              className="px-4 py-2 bg-slate-100 text-slate-700 text-sm rounded-xl hover:bg-slate-200 flex items-center gap-2"
            >
              {clipsLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Refresh'}
            </button>
            <button
              onClick={extractSig}
              disabled={sigLoading}
              className="px-4 py-2 bg-indigo-600 text-white text-sm rounded-xl hover:bg-indigo-700 disabled:opacity-40 flex items-center gap-2"
            >
              {sigLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Extract Top 3 Clips'}
            </button>
          </div>
          {clips.length === 0
            ? <p className="text-sm text-slate-400 card p-6 text-center">No clips extracted yet.</p>
            : (
              <div className="space-y-2">
                {clips.map((c, i) => (
                  <div key={i} className="bg-white rounded-xl border border-slate-200 px-4 py-3 flex items-center gap-3 text-sm">
                    <span className="text-slate-400 font-mono">#{c.segment_index}</span>
                    <span className="flex-1 text-slate-700 font-medium">{c.filename}</span>
                    <a
                      href={c.url}
                      target="_blank"
                      rel="noreferrer"
                      className="text-indigo-600 hover:underline text-xs"
                    >
                      Download
                    </a>
                  </div>
                ))}
              </div>
            )}
        </div>
      ) : (
        /* Speakers tab */
        <div className="space-y-4">
          {speakersLoading
            ? <div className="flex justify-center py-8"><Loader2 className="w-6 h-6 animate-spin text-slate-400" /></div>
            : speakers.length === 0
            ? <p className="text-sm text-slate-400 card p-6 text-center">No speaker data available.</p>
            : (
              <div className="bg-white rounded-2xl border border-slate-200 overflow-hidden">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-slate-100 bg-slate-50">
                      <th className="text-left px-4 py-3 text-xs font-semibold text-slate-500">Speaker</th>
                      <th className="text-right px-4 py-3 text-xs font-semibold text-slate-500">Talk %</th>
                      <th className="text-right px-4 py-3 text-xs font-semibold text-slate-500">Turns</th>
                      <th className="text-right px-4 py-3 text-xs font-semibold text-slate-500">Words</th>
                    </tr>
                  </thead>
                  <tbody>
                    {speakers.map(s => (
                      <tr key={s.speaker} className="border-b border-slate-100 last:border-0">
                        <td className="px-4 py-3 font-medium text-slate-800">{s.speaker}</td>
                        <td className="px-4 py-3 text-right">
                          <div className="flex items-center justify-end gap-2">
                            <div className="w-20 bg-slate-100 rounded-full h-1.5">
                              <div className="h-1.5 rounded-full bg-indigo-400" style={{ width: `${s.percentage}%` }} />
                            </div>
                            <span className="text-slate-600">{s.percentage.toFixed(1)}%</span>
                          </div>
                        </td>
                        <td className="px-4 py-3 text-right text-slate-600">{s.turns}</td>
                        <td className="px-4 py-3 text-right text-slate-600">{s.words.toLocaleString()}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
        </div>
      )}
    </div>
  )
}
