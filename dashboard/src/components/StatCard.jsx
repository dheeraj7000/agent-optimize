/** Headline metric card styled with Supermemory aesthetic. */
export default function StatCard({ label, value, sub, icon: Icon, color = 'green' }) {
  const colorStyles = {
    green: 'bg-emerald-50 text-emerald-700 border-emerald-200/60',
    blue: 'bg-sky-50 text-sky-700 border-sky-200/60',
    cyan: 'bg-cyan-50 text-cyan-700 border-cyan-200/60',
    amber: 'bg-amber-50 text-amber-700 border-amber-200/60',
    red: 'bg-rose-50 text-rose-700 border-rose-200/60',
    gray: 'bg-slate-50 text-slate-600 border-slate-200/60',
  }

  return (
    <div className="bg-white/95 rounded-xl border border-slate-200/80 p-5 shadow-xs hover:border-slate-300/90 transition-all group">
      <div className="flex items-center justify-between">
        <p className="text-[11px] font-mono font-medium uppercase tracking-wider text-slate-500">
          {label}
        </p>
        {Icon && (
          <div className={`p-1.5 rounded-md border ${colorStyles[color] || colorStyles.green}`}>
            <Icon size={15} />
          </div>
        )}
      </div>
      <p className="mt-2 text-2xl font-bold font-mono tracking-tight text-slate-900 tabular-nums">
        {value}
      </p>
      {sub && (
        <p className="mt-1 text-xs font-mono text-slate-400">
          {sub}
        </p>
      )}
    </div>
  )
}
