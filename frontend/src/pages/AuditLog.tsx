import { useState, useEffect } from 'react'
import { Shield, Activity, Filter, BarChart3, Clock, User, Database } from 'lucide-react'
import { queryAudit, getAuditStats, type AuditEntry } from '../api/client'

export function AuditLog() {
  const [entries, setEntries] = useState<AuditEntry[]>([])
  const [stats, setStats] = useState<{ total_entries: number; action_counts: Record<string, number>; resource_counts: Record<string, number> } | null>(null)
  const [filterAction, setFilterAction] = useState('')
  const [filterResource, setFilterResource] = useState('')
  const [loading, setLoading] = useState(true)
  const [page, setPage] = useState(0)
  const limit = 30

  useEffect(() => {
    const load = async () => {
      setLoading(true)
      try {
        const [res, st] = await Promise.all([
          queryAudit({ action: filterAction || undefined, resource_type: filterResource || undefined, limit, offset: page * limit }),
          getAuditStats(),
        ])
        setEntries(res.entries ?? [])
        setStats(st)
      } catch { /* ignore */ }
      setLoading(false)
    }
    load()
  }, [filterAction, filterResource, page])

  const fmtTime = (ts: number) => new Date(ts * 1000).toLocaleString()

  const actionIcons: Record<string, string> = {
    create: '🟢', update: '🔵', delete: '🔴', login: '🟡', export: '🟠',
  }

  return (
    <div className="p-8 animate-fade-in">
      {/* Header */}
      <div className="relative mb-8 bg-gradient-to-br from-violet-600 via-violet-700 to-purple-800 rounded-2xl p-7 overflow-hidden shadow-lg shadow-violet-900/20">
        <div className="relative">
          <div className="flex items-center gap-2.5 mb-2">
            <div className="w-2 h-2 rounded-full bg-violet-300 animate-pulse" />
            <span className="text-xs font-semibold text-violet-200 uppercase tracking-widest">Security</span>
          </div>
          <h1 className="text-2xl font-bold text-white tracking-tight">Audit Log</h1>
          <p className="text-violet-200 text-sm mt-1">Complete activity trail across the platform</p>
        </div>
      </div>

      {/* Stats */}
      {stats && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
          <div className="bg-white rounded-xl border border-slate-200 p-4 shadow-sm">
            <div className="flex items-center gap-2 mb-1"><Activity className="w-4 h-4 text-violet-600" /><span className="text-xs text-slate-500 font-medium">Total Events</span></div>
            <p className="text-xl font-bold text-slate-700">{stats.total_entries}</p>
          </div>
          {Object.entries(stats.action_counts).slice(0, 3).map(([k, v]) => (
            <div key={k} className="bg-white rounded-xl border border-slate-200 p-4 shadow-sm">
              <div className="flex items-center gap-2 mb-1"><span className="text-sm">{actionIcons[k] ?? '⚪'}</span><span className="text-xs text-slate-500 font-medium capitalize">{k}</span></div>
              <p className="text-xl font-bold text-slate-700">{v}</p>
            </div>
          ))}
        </div>
      )}

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-3 mb-6">
        <Filter className="w-4 h-4 text-slate-400" />
        <input value={filterAction} onChange={e => { setFilterAction(e.target.value); setPage(0) }} placeholder="Filter by action…" className="px-3 py-1.5 rounded-lg border border-slate-200 text-sm w-48 shadow-sm" />
        <input value={filterResource} onChange={e => { setFilterResource(e.target.value); setPage(0) }} placeholder="Filter by resource…" className="px-3 py-1.5 rounded-lg border border-slate-200 text-sm w-48 shadow-sm" />
      </div>

      {/* Table */}
      {loading ? (
        <p className="text-center py-16 text-slate-400 text-sm">Loading audit trail…</p>
      ) : entries.length === 0 ? (
        <div className="text-center py-16">
          <Shield className="w-10 h-10 text-slate-300 mx-auto mb-3" />
          <p className="text-slate-500 text-sm">No audit entries match the current filters.</p>
        </div>
      ) : (
        <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-100 bg-slate-50/50">
                <th className="text-left px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wider">Time</th>
                <th className="text-left px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wider">Action</th>
                <th className="text-left px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wider">Resource</th>
                <th className="text-left px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wider">User</th>
                <th className="text-left px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wider">Details</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {entries.map(e => (
                <tr key={e.id} className="hover:bg-slate-50/50 transition">
                  <td className="px-4 py-3 text-xs text-slate-500 whitespace-nowrap"><Clock className="w-3 h-3 inline mr-1" />{fmtTime(e.timestamp)}</td>
                  <td className="px-4 py-3"><span className="px-2 py-0.5 rounded text-xs font-bold bg-indigo-100 text-indigo-700">{e.action}</span></td>
                  <td className="px-4 py-3 text-xs text-slate-600"><Database className="w-3 h-3 inline mr-1" />{e.resource_type} / {e.resource_id.slice(0, 8)}…</td>
                  <td className="px-4 py-3 text-xs text-slate-600"><User className="w-3 h-3 inline mr-1" />{e.user_id}</td>
                  <td className="px-4 py-3 text-xs text-slate-400 max-w-[200px] truncate">{JSON.stringify(e.details)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Pagination */}
      <div className="flex items-center justify-center gap-3 mt-6">
        <button onClick={() => setPage(Math.max(0, page - 1))} disabled={page === 0} className="px-3 py-1 text-sm rounded-lg bg-slate-100 text-slate-600 disabled:opacity-40 hover:bg-slate-200 transition">← Prev</button>
        <span className="text-sm text-slate-500">Page {page + 1}</span>
        <button onClick={() => setPage(page + 1)} disabled={entries.length < limit} className="px-3 py-1 text-sm rounded-lg bg-slate-100 text-slate-600 disabled:opacity-40 hover:bg-slate-200 transition">Next →</button>
      </div>
    </div>
  )
}
