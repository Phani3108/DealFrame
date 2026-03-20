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
      {/* Sidebar */}
      <aside className="w-64 bg-white border-r border-slate-200 flex flex-col flex-shrink-0 shadow-sm">
        {/* Logo */}
        <div className="px-5 py-5 border-b border-slate-100">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 bg-gradient-to-br from-indigo-500 to-indigo-700 rounded-xl flex items-center justify-center shadow-sm">
              <Activity className="w-5 h-5 text-white" />
            </div>
            <div>
              <p className="font-bold text-slate-900 text-sm leading-tight tracking-tight">TemporalOS</p>
              <p className="text-xs text-slate-400 leading-tight">Decision Intelligence</p>
            </div>
          </div>
        </div>

        {/* Nav */}
        <nav className="flex-1 px-3 py-3 overflow-y-auto">
          {navGroups.map(({ label, items }) => (
            <div key={label} className="mb-5">
              <p className="px-3 mb-1.5 text-[10px] font-semibold uppercase tracking-widest text-slate-400">
                {label}
              </p>
              <div className="space-y-0.5">
                {items.map(({ to, label: itemLabel, icon: Icon }) => (
                  <NavLink
                    key={to}
                    to={to}
                    end={to === '/'}
                    className={({ isActive }) =>
                      `flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-all duration-150 ${
                        isActive
                          ? 'bg-indigo-50 text-indigo-700 shadow-sm'
                          : 'text-slate-600 hover:bg-slate-50 hover:text-slate-900'
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
        <div className="px-4 py-3 border-t border-slate-100">
          <a
            href="/docs"
            target="_blank"
            rel="noreferrer"
            className="flex items-center gap-1.5 text-xs text-slate-400 hover:text-indigo-600 transition-colors"
          >
            <span>API Docs</span>
            <span className="text-slate-300">↗</span>
          </a>
          <p className="text-xs text-slate-300 mt-1">v0.1.0 · 10 Phases</p>
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 overflow-auto bg-slate-50">
        {children}
      </main>
    </div>
  )
}

