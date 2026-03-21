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
} from 'lucide-react'

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
    ],
  },
]

interface LayoutProps {
  children: React.ReactNode
}

export function Layout({ children }: LayoutProps) {
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
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 overflow-auto bg-slate-50">
        {children}
      </main>
    </div>
  )
}

