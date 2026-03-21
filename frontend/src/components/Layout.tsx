import { useState, useEffect } from 'react'
import { NavLink } from 'react-router-dom'
import {
  LayoutDashboard,
  Upload,
  Eye,
  Brain,
  Zap,
  Cpu,
  Activity,
  BarChart3,
  Search,
  Radio,
  MessageSquare,
  Target,
  Layers,
  Calendar,
  Network,
  Settings,
  Plug,
  MessageSquareText,
  ListChecks,
  Shield,
  GitCompare,
  TrendingUp,
  Bot,
  ShieldCheck,
  Bell,
} from 'lucide-react'
import { getNotifications, markAllNotificationsRead } from '../api/client'

const navGroups = [
  {
    label: 'Core',
    items: [
      { to: '/', label: 'Dashboard', icon: LayoutDashboard },
      { to: '/upload', label: 'Upload & Process', icon: Upload },
      { to: '/observatory', label: 'Observatory', icon: Eye },
    ],
  },
  {
    label: 'Intelligence',
    items: [
      { to: '/intelligence', label: 'Analytics', icon: Brain },
      { to: '/search', label: 'Search', icon: Search },
      { to: '/patterns', label: 'Pattern Miner', icon: TrendingUp },
      { to: '/diff', label: 'Diff Engine', icon: GitCompare },
    ],
  },
  {
    label: 'Capabilities',
    items: [
      { to: '/chat', label: 'Ask Library', icon: MessageSquare },
      { to: '/coaching', label: 'Coaching', icon: Target },
      { to: '/copilot', label: 'Live Copilot', icon: Bot },
      { to: '/batch', label: 'Batch', icon: Layers },
      { to: '/meeting-prep', label: 'Meeting Prep', icon: Calendar },
      { to: '/knowledge-graph', label: 'Knowledge Graph', icon: Network },
      { to: '/schema-builder', label: 'Schema Builder', icon: Settings },
    ],
  },
  {
    label: 'Models',
    items: [
      { to: '/finetuning', label: 'Fine-tuning', icon: Zap },
      { to: '/local', label: 'Local Pipeline', icon: Cpu },
      { to: '/streaming', label: 'Live Stream', icon: Radio },
    ],
  },
  {
    label: 'Platform',
    items: [
      { to: '/observability', label: 'Observability', icon: BarChart3 },
      { to: '/integrations', label: 'Connections', icon: Plug },
      { to: '/annotations', label: 'Annotations', icon: MessageSquareText },
      { to: '/review-queue', label: 'Review Queue', icon: ListChecks },
      { to: '/audit-log', label: 'Audit Log', icon: Shield },
      { to: '/admin', label: 'Admin', icon: ShieldCheck },
      { to: '/settings', label: 'Settings', icon: Settings },
    ],
  },
]

interface LayoutProps {
  children: React.ReactNode
}

export function Layout({ children }: LayoutProps) {
  const [unread, setUnread] = useState(0)
  const [showNotifs, setShowNotifs] = useState(false)
  const [notifs, setNotifs] = useState<Array<{ id: string; type: string; title: string; message: string; read: boolean; created_at: number }>>([])

  useEffect(() => {
    getNotifications('default', true)
      .then(r => { setUnread(r.unread_count ?? 0); setNotifs(r.notifications ?? []) })
      .catch(() => {})
    const iv = setInterval(() => {
      getNotifications('default', true)
        .then(r => { setUnread(r.unread_count ?? 0); setNotifs(r.notifications ?? []) })
        .catch(() => {})
    }, 30000)
    return () => clearInterval(iv)
  }, [])

  const handleMarkAll = async () => {
    await markAllNotificationsRead('default').catch(() => {})
    setUnread(0)
    setNotifs([])
  }

  return (
    <div className="flex h-screen bg-slate-50 overflow-hidden">
      {/* Dark Sidebar */}
      <aside className="w-60 bg-[#0a0f1e] flex flex-col flex-shrink-0">
        {/* Logo */}
        <div className="px-5 py-5 border-b border-white/[0.06]">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 bg-gradient-to-br from-indigo-400 via-indigo-500 to-violet-600 rounded-xl flex items-center justify-center shadow-lg shadow-indigo-900/50 flex-shrink-0">
              <Activity className="w-5 h-5 text-white" />
            </div>
            <div>
              <p className="font-bold text-white text-sm leading-tight tracking-tight">TemporalOS</p>
              <p className="text-[10px] text-slate-500 leading-tight mt-0.5">Decision Intelligence</p>
            </div>
          </div>
        </div>

        {/* Nav */}
        <nav className="flex-1 px-3 py-4 overflow-y-auto">
          {navGroups.map(({ label, items }) => (
            <div key={label} className="mb-5">
              <p className="px-2.5 mb-1.5 text-[9px] font-bold uppercase tracking-[0.12em] text-slate-600">
                {label}
              </p>
              <div className="space-y-0.5">
                {items.map(({ to, label: itemLabel, icon: Icon }) => (
                  <NavLink
                    key={to}
                    to={to}
                    end={to === '/'}
                    className={({ isActive }) =>
                      `flex items-center gap-2.5 px-2.5 py-2 rounded-lg text-[13px] font-medium transition-all duration-150 ${
                        isActive
                          ? 'bg-indigo-500/15 text-indigo-300 border border-indigo-500/25 shadow-sm'
                          : 'text-slate-400 hover:bg-white/[0.05] hover:text-slate-200'
                      }`
                    }
                  >
                    <Icon className="w-4 h-4 flex-shrink-0" />
                    {itemLabel}
                  </NavLink>
                ))}
              </div>
            </div>
          ))}
        </nav>

        {/* Footer */}
        <div className="px-4 py-4 border-t border-white/[0.06]">
          <a
            href="/docs"
            target="_blank"
            rel="noreferrer"
            className="flex items-center gap-1 text-xs text-slate-600 hover:text-indigo-400 transition-colors w-fit"
          >
            API Docs ↗
          </a>
          <p className="text-[10px] text-slate-700 mt-1.5">v0.1.0 · 10 Phases</p>
          {/* Copyright — do not remove */}
          <div className="mt-3 pt-3 border-t border-white/[0.04]">
            <p className="text-[9px] text-slate-700 leading-tight">
              © 2024-2026{' '}
              <a
                href="https://linkedin.com/in/phani-marupaka"
                target="_blank"
                rel="noreferrer"
                className="hover:text-indigo-400 transition-colors"
              >
                Phani Marupaka
              </a>
            </p>
            <a
              href="https://phanimarupaka.netlify.app"
              target="_blank"
              rel="noreferrer"
              className="text-[9px] text-slate-700 hover:text-indigo-400 transition-colors"
            >
              phanimarupaka.netlify.app ↗
            </a>
          </div>
        </div>
      </aside>

      {/* Main content */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Top bar with notification bell */}
        <header className="flex items-center justify-end px-6 py-2.5 border-b border-slate-200 bg-white flex-shrink-0">
          <div className="relative">
            <button
              onClick={() => setShowNotifs(!showNotifs)}
              className="relative p-2 rounded-lg hover:bg-slate-100 text-slate-500 hover:text-slate-700 transition"
            >
              <Bell className="w-5 h-5" />
              {unread > 0 && (
                <span className="absolute -top-0.5 -right-0.5 w-4.5 h-4.5 bg-red-500 text-white text-[10px] font-bold rounded-full flex items-center justify-center animate-pulse">
                  {unread > 9 ? '9+' : unread}
                </span>
              )}
            </button>
            {showNotifs && (
              <div className="absolute right-0 mt-1 w-80 bg-white rounded-xl border border-slate-200 shadow-lg z-50 overflow-hidden">
                <div className="flex items-center justify-between px-4 py-3 border-b border-slate-100">
                  <span className="text-sm font-bold text-slate-700">Notifications</span>
                  {unread > 0 && (
                    <button onClick={handleMarkAll} className="text-xs text-indigo-500 hover:text-indigo-700 font-medium transition">Mark all read</button>
                  )}
                </div>
                <div className="max-h-64 overflow-y-auto">
                  {notifs.length === 0 ? (
                    <p className="text-sm text-slate-400 text-center py-6">All caught up!</p>
                  ) : (
                    notifs.slice(0, 10).map(n => (
                      <div key={n.id} className="px-4 py-3 border-b border-slate-50 last:border-0 hover:bg-slate-50/50">
                        <p className="text-xs font-semibold text-slate-700">{n.title}</p>
                        <p className="text-xs text-slate-500 mt-0.5 line-clamp-2">{n.message}</p>
                      </div>
                    ))
                  )}
                </div>
              </div>
            )}
          </div>
        </header>
        <main className="flex-1 overflow-auto bg-slate-50">
          {children}
        </main>
      </div>
    </div>
  )
}

