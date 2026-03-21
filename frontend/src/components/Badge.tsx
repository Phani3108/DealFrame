interface BadgeConfig {
  bg: string
  text: string
  dot: string
  pulse?: boolean
}

const config: Record<string, BadgeConfig> = {
  high:       { bg: 'bg-red-50 border border-red-200',     text: 'text-red-700',     dot: 'bg-red-500' },
  medium:     { bg: 'bg-amber-50 border border-amber-200', text: 'text-amber-700',   dot: 'bg-amber-500' },
  low:        { bg: 'bg-emerald-50 border border-emerald-200', text: 'text-emerald-700', dot: 'bg-emerald-500' },
  pending:    { bg: 'bg-slate-100 border border-slate-200', text: 'text-slate-600',  dot: 'bg-slate-400' },
  processing: { bg: 'bg-blue-50 border border-blue-200',   text: 'text-blue-700',   dot: 'bg-blue-500', pulse: true },
  completed:  { bg: 'bg-emerald-50 border border-emerald-200', text: 'text-emerald-700', dot: 'bg-emerald-500' },
  failed:     { bg: 'bg-red-50 border border-red-200',     text: 'text-red-700',     dot: 'bg-red-500' },
  running:    { bg: 'bg-indigo-50 border border-indigo-200', text: 'text-indigo-700', dot: 'bg-indigo-500', pulse: true },
  activated:  { bg: 'bg-emerald-50 border border-emerald-200', text: 'text-emerald-700', dot: 'bg-emerald-500' },
}

interface BadgeProps {
  label: string
  className?: string
}

export function Badge({ label, className = '' }: BadgeProps) {
  const key = label.toLowerCase()
  const c = config[key] ?? { bg: 'bg-slate-100 border border-slate-200', text: 'text-slate-600', dot: 'bg-slate-400' }
  return (
    <span
      className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold ${c.bg} ${c.text} ${className}`}
    >
      <span className={`w-1.5 h-1.5 rounded-full ${c.dot} flex-shrink-0 ${c.pulse ? 'animate-pulse' : ''}`} />
      {label}
    </span>
  )
}

export function RiskBadge({ risk }: { risk: 'high' | 'medium' | 'low' }) {
  return <Badge label={risk} />
}
