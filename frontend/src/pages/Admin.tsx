import { useState, useEffect } from 'react'
import { ShieldCheck, Users, Building2, Key, BarChart3, Settings as SettingsIcon, RefreshCw, Activity } from 'lucide-react'
import {
  getAdminTenants,
  getAdminUsers,
  getAdminRoles,
  getAdminSettings,
  getSystemStats,
} from '../api/client'

type Tab = 'overview' | 'tenants' | 'users' | 'roles' | 'settings'

export function Admin() {
  const [tab, setTab] = useState<Tab>('overview')
  const [stats, setStats] = useState<Record<string, number> | null>(null)
  const [tenants, setTenants] = useState<Array<{ tenant_id: string; slug: string; plan: string; max_videos: number; max_users: number }>>([])
  const [users, setUsers] = useState<Array<{ email: string; display_name: string; role: string; tier: string; created_at: string }>>([])
  const [roles, setRoles] = useState<Record<string, string[]>>({})
  const [settings, setSettings] = useState<Record<string, unknown> | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const load = async () => {
      setLoading(true)
      try {
        if (tab === 'overview') {
          const s = await getSystemStats()
          setStats(s as any)
        } else if (tab === 'tenants') {
          const r = await getAdminTenants()
          setTenants(r.tenants ?? [])
        } else if (tab === 'users') {
          const r = await getAdminUsers()
          setUsers(r.users ?? [])
        } else if (tab === 'roles') {
          const r = await getAdminRoles()
          setRoles(r.roles ?? {})
        } else if (tab === 'settings') {
          const r = await getAdminSettings()
          setSettings(r)
        }
      } catch { /* ignore */ }
      setLoading(false)
    }
    load()
  }, [tab])

  const tabs: { key: Tab; label: string; icon: typeof Users }[] = [
    { key: 'overview', label: 'Overview', icon: BarChart3 },
    { key: 'tenants', label: 'Tenants', icon: Building2 },
    { key: 'users', label: 'Users', icon: Users },
    { key: 'roles', label: 'Roles & Permissions', icon: Key },
    { key: 'settings', label: 'Settings', icon: SettingsIcon },
  ]

  return (
    <div className="p-8 animate-fade-in">
      {/* Header */}
      <div className="relative mb-8 bg-gradient-to-br from-slate-700 via-slate-800 to-slate-900 rounded-2xl p-7 overflow-hidden shadow-lg shadow-slate-900/30">
        <div className="relative">
          <div className="flex items-center gap-2.5 mb-2">
            <div className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
            <span className="text-xs font-semibold text-slate-300 uppercase tracking-widest">Administration</span>
          </div>
          <h1 className="text-2xl font-bold text-white tracking-tight">Admin Console</h1>
          <p className="text-slate-400 text-sm mt-1">Manage tenants, users, roles, and platform settings</p>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex items-center gap-1 mb-6 bg-slate-100 p-1 rounded-xl w-fit">
        {tabs.map(({ key, label, icon: Icon }) => (
          <button
            key={key}
            onClick={() => setTab(key)}
            className={`flex items-center gap-1.5 px-4 py-2 text-sm font-medium rounded-lg transition ${tab === key ? 'bg-white text-slate-800 shadow-sm' : 'text-slate-500 hover:text-slate-700'}`}
          >
            <Icon className="w-4 h-4" /> {label}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="flex items-center justify-center py-16"><RefreshCw className="w-5 h-5 text-slate-400 animate-spin" /></div>
      ) : (
        <>
          {/* Overview */}
          {tab === 'overview' && stats && (
            <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
              {Object.entries(stats).map(([key, val]) => (
                <div key={key} className="bg-white rounded-xl border border-slate-200 p-5 shadow-sm">
                  <div className="flex items-center gap-2 mb-2">
                    <Activity className="w-4 h-4 text-indigo-500" />
                    <span className="text-xs font-medium text-slate-500 capitalize">{key.replace(/_/g, ' ')}</span>
                  </div>
                  <p className="text-2xl font-bold text-slate-700">{val}</p>
                </div>
              ))}
            </div>
          )}

          {/* Tenants */}
          {tab === 'tenants' && (
            <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
              <table className="w-full text-sm">
                <thead><tr className="border-b border-slate-100 bg-slate-50/50">
                  <th className="text-left px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wider">Slug</th>
                  <th className="text-left px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wider">Plan</th>
                  <th className="text-left px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wider">Max Videos</th>
                  <th className="text-left px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wider">Max Users</th>
                </tr></thead>
                <tbody className="divide-y divide-slate-100">
                  {tenants.map(t => (
                    <tr key={t.tenant_id} className="hover:bg-slate-50/50 transition">
                      <td className="px-4 py-3 font-medium text-slate-700"><Building2 className="w-3.5 h-3.5 inline mr-1.5 text-slate-400" />{t.slug}</td>
                      <td className="px-4 py-3"><span className={`px-2 py-0.5 rounded text-xs font-bold ${t.plan === 'enterprise' ? 'bg-indigo-100 text-indigo-700' : t.plan === 'pro' ? 'bg-blue-100 text-blue-700' : 'bg-slate-100 text-slate-600'}`}>{t.plan}</span></td>
                      <td className="px-4 py-3 text-slate-600">{t.max_videos}</td>
                      <td className="px-4 py-3 text-slate-600">{t.max_users}</td>
                    </tr>
                  ))}
                  {tenants.length === 0 && <tr><td colSpan={4} className="px-4 py-8 text-center text-slate-400">No tenants configured</td></tr>}
                </tbody>
              </table>
            </div>
          )}

          {/* Users */}
          {tab === 'users' && (
            <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
              <table className="w-full text-sm">
                <thead><tr className="border-b border-slate-100 bg-slate-50/50">
                  <th className="text-left px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wider">User</th>
                  <th className="text-left px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wider">Role</th>
                  <th className="text-left px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wider">Tier</th>
                  <th className="text-left px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wider">Created</th>
                </tr></thead>
                <tbody className="divide-y divide-slate-100">
                  {users.map(u => (
                    <tr key={u.email} className="hover:bg-slate-50/50 transition">
                      <td className="px-4 py-3">
                        <p className="font-medium text-slate-700">{u.display_name}</p>
                        <p className="text-xs text-slate-400">{u.email}</p>
                      </td>
                      <td className="px-4 py-3"><span className="px-2 py-0.5 rounded text-xs font-bold bg-violet-100 text-violet-700">{u.role}</span></td>
                      <td className="px-4 py-3 text-slate-600 capitalize">{u.tier}</td>
                      <td className="px-4 py-3 text-xs text-slate-400">{u.created_at}</td>
                    </tr>
                  ))}
                  {users.length === 0 && <tr><td colSpan={4} className="px-4 py-8 text-center text-slate-400">No users found</td></tr>}
                </tbody>
              </table>
            </div>
          )}

          {/* Roles */}
          {tab === 'roles' && (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {Object.entries(roles).map(([role, perms]) => (
                <div key={role} className="bg-white rounded-xl border border-slate-200 p-5 shadow-sm">
                  <div className="flex items-center gap-2 mb-3">
                    <ShieldCheck className="w-4 h-4 text-violet-500" />
                    <span className="font-bold text-slate-700 capitalize">{role}</span>
                    <span className="ml-auto text-xs text-slate-400">{perms.length} permissions</span>
                  </div>
                  <div className="flex flex-wrap gap-1.5">
                    {perms.map(p => (
                      <span key={p} className="px-2 py-0.5 rounded text-[11px] font-medium bg-slate-100 text-slate-600">{p}</span>
                    ))}
                  </div>
                </div>
              ))}
              {Object.keys(roles).length === 0 && <p className="text-slate-400 text-sm col-span-2 text-center py-8">No roles configured</p>}
            </div>
          )}

          {/* Settings */}
          {tab === 'settings' && settings && (
            <div className="bg-white rounded-xl border border-slate-200 p-6 shadow-sm">
              <div className="space-y-3">
                {Object.entries(settings).map(([key, val]) => (
                  <div key={key} className="flex items-center justify-between py-2 border-b border-slate-100 last:border-0">
                    <span className="text-sm font-medium text-slate-700">{key}</span>
                    <span className="text-sm font-mono text-slate-500 max-w-[300px] truncate">{String(val)}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  )
}
