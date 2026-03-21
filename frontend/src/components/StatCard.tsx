interface StatCardProps {
  label: string
  value: string | number
  icon: React.ComponentType<{ className?: string }>
  iconBg: string
  iconColor: string
  trend?: string
  trendPositive?: boolean
}

export function StatCard({
  label, value, icon: Icon, iconBg, iconColor, trend, trendPositive = true,
}: StatCardProps) {
  return (
    <div className="bg-white border border-slate-200 rounded-2xl p-5 shadow-sm hover:shadow-md hover:border-slate-300 transition-all duration-200 group">
      <div className="flex items-start justify-between mb-4">
        <div className={`${iconBg} w-11 h-11 rounded-xl flex items-center justify-center flex-shrink-0 shadow-sm`}>
          <Icon className={`w-5 h-5 ${iconColor}`} />
        </div>
        {trend && (
          <span className={`text-xs font-semibold px-2.5 py-1 rounded-full border ${
            trendPositive
              ? 'bg-emerald-50 text-emerald-700 border-emerald-100'
              : 'bg-red-50 text-red-700 border-red-100'
          }`}>
            {trend}
          </span>
        )}
      </div>
      <p className="text-3xl font-bold text-slate-900 tabular-nums leading-none">{value}</p>
      <p className="text-xs text-slate-500 mt-2 font-semibold uppercase tracking-wider">{label}</p>
    </div>
  )
}
