import { useEffect, useState } from 'react'
import {
  getDriftReport,
  getCalibrationReport,
  getReviewQueue,
  type DriftReport,
  type CalibrationReport,
} from '../api/client'
import { AlertTriangle, CheckCircle, Activity, BarChart2, Users, RefreshCw } from 'lucide-react'

function DriftStatusCard({ report }: { report: DriftReport | null }) {
  if (!report) return <div className="h-32 bg-slate-100 rounded-xl animate-pulse" />
  return (
    <div className={`rounded-xl border p-5 ${report.any_drift ? 'border-red-200 bg-red-50' : 'border-emerald-200 bg-emerald-50'}`}>
      <div className="flex items-start justify-between">
        <div>
          <p className="text-sm font-medium text-slate-600 mb-1">Distribution Drift</p>
          <p className={`text-2xl font-bold ${report.any_drift ? 'text-red-700' : 'text-emerald-700'}`}>
            {report.any_drift ? 'DRIFT DETECTED' : 'All Clear'}
          </p>
          <p className="text-xs text-slate-500 mt-1">
            {report.total_recorded} samples recorded · Baseline {report.baseline_frozen ? 'frozen' : 'building'}
          </p>
        </div>
        {report.any_drift
          ? <AlertTriangle className="w-8 h-8 text-red-500 flex-shrink-0" />
          : <CheckCircle className="w-8 h-8 text-emerald-500 flex-shrink-0" />}
      </div>
      {report.alerts.map((a, i) => (
        <div key={i} className="mt-3 pt-3 border-t border-white/60">
          <div className="flex items-center justify-between mb-1">
            <span className="text-xs font-medium text-slate-700">{a.metric.replace(/_/g, ' ')}</span>
            <span className={`text-xs font-semibold px-2 py-0.5 rounded-full ${a.is_drifted ? 'bg-red-100 text-red-700' : 'bg-emerald-100 text-emerald-700'}`}>
              {a.is_drifted ? 'DRIFTED' : 'STABLE'}
            </span>
          </div>
          <div className="w-full bg-white/70 rounded-full h-1.5">
            <div
              className={`h-1.5 rounded-full transition-all ${a.is_drifted ? 'bg-red-500' : 'bg-emerald-500'}`}
              style={{ width: `${Math.min(a.drift_score * 100, 100)}%` }}
            />
          </div>
          <p className="text-xs text-slate-500 mt-1">{a.message}</p>
        </div>
      ))}
      {report.alerts.length === 0 && (
        <p className="text-xs text-slate-500 mt-3 pt-3 border-t border-white/60">
          Not enough samples to run statistical tests yet (need {report.baseline_size < 100 ? `${100 - report.baseline_size} more` : 'window data'}).
        </p>
      )}
    </div>
  )
}

function CalibrationPanel({ report }: { report: CalibrationReport | null }) {
  if (!report) return <div className="h-48 bg-slate-100 rounded-xl animate-pulse" />
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-5">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h3 className="text-sm font-semibold text-slate-900">Confidence Calibration</h3>
          <p className="text-xs text-slate-500">Expected Calibration Error (ECE) — lower is better</p>
        </div>
        <div className="text-right">
          <p className="text-2xl font-bold text-slate-900">{report.ece.toFixed(3)}</p>
          <p className="text-xs text-slate-500">{report.total_samples} samples</p>
        </div>
      </div>
      {report.bins.length > 0 ? (
        <div className="space-y-2">
          {report.bins.map((bin, i) => (
            <div key={i} className="flex items-center gap-3">
              <span className="text-xs text-slate-400 w-16 flex-shrink-0">{bin.lower}–{bin.upper}</span>
              <div className="flex-1 h-4 bg-slate-100 rounded-full overflow-hidden relative">
                <div
                  className="absolute inset-y-0 left-0 bg-indigo-200 rounded-full"
                  style={{ width: `${bin.mean_confidence * 100}%` }}
                />
                <div
                  className="absolute inset-y-0 left-0 bg-indigo-600 rounded-full opacity-70"
                  style={{ width: `${bin.accuracy * 100}%` }}
                />
              </div>
              <span className="text-xs text-slate-500 w-20 text-right flex-shrink-0">
                {(bin.accuracy * 100).toFixed(0)}% acc / {bin.count}
              </span>
            </div>
          ))}
          <div className="flex gap-4 pt-1 text-xs text-slate-400">
            <span className="flex items-center gap-1"><span className="w-3 h-2 rounded bg-indigo-200 inline-block" /> Predicted confidence</span>
            <span className="flex items-center gap-1"><span className="w-3 h-2 rounded bg-indigo-600 opacity-70 inline-block" /> Actual accuracy</span>
          </div>
        </div>
      ) : (
        <p className="text-sm text-slate-400 text-center py-6">
          No calibration data yet — add samples via POST /api/v1/observability/calibration/sample
        </p>
      )}
    </div>
  )
}

export function Observability() {
  const [drift, setDrift] = useState<DriftReport | null>(null)
  const [calibration, setCalibration] = useState<CalibrationReport | null>(null)
  const [queue, setQueue] = useState<{ queue_depth: number; threshold: number } | null>(null)
  const [loading, setLoading] = useState(true)
  const [lastRefresh, setLastRefresh] = useState(new Date())

  const load = async () => {
    setLoading(true)
    try {
      const [d, c, q] = await Promise.allSettled([getDriftReport(), getCalibrationReport(), getReviewQueue()])
      if (d.status === 'fulfilled') setDrift(d.value)
      if (c.status === 'fulfilled') setCalibration(c.value)
      if (q.status === 'fulfilled') setQueue(q.value)
      setLastRefresh(new Date())
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  return (
    <div className="p-4 sm:p-6 lg:p-8 max-w-6xl animate-fade-in">
      {/* Header */}
      <div className="flex items-start justify-between mb-8">
        <div>
          <h1 className="page-title">Observability</h1>
          <p className="page-subtitle">Prometheus metrics · drift detection · confidence calibration · review queue</p>
        </div>
        <div className="flex items-center gap-3">
          <span className="text-xs text-slate-400">
            Refreshed {lastRefresh.toLocaleTimeString()}
          </span>
          <button
            onClick={load}
            disabled={loading}
            className="btn-secondary flex items-center gap-1.5"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
            Refresh
          </button>
        </div>
      </div>

      {/* Quick stat row */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 mb-8">
        <div className="bg-white rounded-xl border border-slate-200 p-4">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 bg-blue-50 rounded-lg flex items-center justify-center">
              <Activity className="w-4 h-4 text-blue-600" />
            </div>
            <div>
              <p className="text-xs text-slate-500">Total Recorded</p>
              <p className="text-xl font-bold text-slate-900">{drift?.total_recorded ?? '—'}</p>
            </div>
          </div>
        </div>
        <div className="bg-white rounded-xl border border-slate-200 p-4">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 bg-violet-50 rounded-lg flex items-center justify-center">
              <BarChart2 className="w-4 h-4 text-violet-600" />
            </div>
            <div>
              <p className="text-xs text-slate-500">Calibration ECE</p>
              <p className="text-xl font-bold text-slate-900">{calibration ? calibration.ece.toFixed(3) : '—'}</p>
            </div>
          </div>
        </div>
        <div className="bg-white rounded-xl border border-slate-200 p-4">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 bg-amber-50 rounded-lg flex items-center justify-center">
              <Users className="w-4 h-4 text-amber-600" />
            </div>
            <div>
              <p className="text-xs text-slate-500">Review Queue</p>
              <p className="text-xl font-bold text-slate-900">{queue?.queue_depth ?? '—'}</p>
            </div>
          </div>
        </div>
      </div>

      {/* Main panels */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
        <DriftStatusCard report={drift} />
        <CalibrationPanel report={calibration} />
      </div>

      {/* Prometheus metrics info */}
      <div className="bg-slate-900 rounded-xl p-5 text-sm">
        <p className="text-slate-400 text-xs font-semibold uppercase tracking-wider mb-3">Prometheus Integration</p>
        <p className="text-slate-300 mb-2">Metrics available at <code className="text-indigo-400">/api/v1/metrics</code> in Prometheus text format.</p>
        <div className="grid grid-cols-2 gap-2 mt-3">
          {[
            'temporalos_extractions_total',
            'temporalos_extraction_confidence',
            'temporalos_stage_latency_ms',
            'temporalos_cost_usd_total',
            'temporalos_videos_processed_total',
            'temporalos_active_jobs',
          ].map(m => (
            <code key={m} className="text-xs text-emerald-400 bg-slate-800 px-2 py-1 rounded">{m}</code>
          ))}
        </div>
        <p className="text-slate-500 text-xs mt-3">
          Configure Grafana Agent with <code className="text-slate-400">scrape_configs</code> targeting this endpoint.
        </p>
      </div>
    </div>
  )
}
