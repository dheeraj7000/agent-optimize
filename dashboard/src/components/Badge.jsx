/** Status / priority / confidence badges styled with Supermemory aesthetic. */
const styles = {
  // Status
  pending: 'bg-amber-50 text-amber-800 border-amber-200/80',
  accepted: 'bg-sky-50 text-sky-800 border-sky-200/80',
  rejected: 'bg-rose-50 text-rose-800 border-rose-200/80',
  replaying: 'bg-indigo-50 text-indigo-800 border-indigo-200/80',
  validated: 'bg-emerald-50 text-emerald-800 border-emerald-200/80',
  deployed: 'bg-teal-50 text-teal-800 border-teal-200/80',
  verified: 'bg-emerald-100 text-emerald-900 border-emerald-300/90 font-semibold',
  rolled_back: 'bg-rose-100 text-rose-900 border-rose-300/90',

  // Priority
  critical: 'bg-rose-50 text-rose-800 border-rose-200/80',
  high: 'bg-amber-50 text-amber-800 border-amber-200/80',
  medium: 'bg-sky-50 text-sky-800 border-sky-200/80',
  low: 'bg-slate-50 text-slate-700 border-slate-200/80',

  // Verdicts
  pass: 'bg-emerald-50 text-emerald-800 border-emerald-200/80',
  fail: 'bg-rose-50 text-rose-800 border-rose-200/80',
  warn: 'bg-amber-50 text-amber-800 border-amber-200/80',
  skip: 'bg-slate-50 text-slate-500 border-slate-200/80',

  // Autopilot
  off: 'bg-slate-50 text-slate-500 border-slate-200/80',
  suggest: 'bg-sky-50 text-sky-800 border-sky-200/80',
  supervised: 'bg-amber-50 text-amber-800 border-amber-200/80',
  autonomous: 'bg-gradient-to-r from-emerald-50 to-teal-50 text-emerald-900 border-emerald-300/80',

  // Canary
  running: 'bg-sky-50 text-sky-800 border-sky-200/80',
  healthy: 'bg-emerald-50 text-emerald-800 border-emerald-200/80',
  degraded: 'bg-amber-50 text-amber-800 border-amber-200/80',
  regressed: 'bg-rose-50 text-rose-800 border-rose-200/80',
  completed: 'bg-emerald-100 text-emerald-900 border-emerald-300/90',
}

const dotColors = {
  validated: 'bg-emerald-500',
  deployed: 'bg-teal-500',
  verified: 'bg-emerald-500',
  pass: 'bg-emerald-500',
  healthy: 'bg-emerald-500',
  completed: 'bg-emerald-500',
  running: 'bg-sky-500 animate-pulse',
  replaying: 'bg-indigo-500 animate-pulse',
  autonomous: 'bg-emerald-500',
  critical: 'bg-rose-500',
  fail: 'bg-rose-500',
  regressed: 'bg-rose-500',
  rejected: 'bg-rose-500',
  pending: 'bg-amber-500',
  warn: 'bg-amber-500',
}

export default function Badge({ value, className = '' }) {
  if (!value) return null
  const s = styles[value] || 'bg-slate-50 text-slate-700 border-slate-200/80'
  const dot = dotColors[value]

  return (
    <span
      className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-md text-[11px] font-mono tracking-tight border ${s} ${className}`}
    >
      {dot && <span className={`w-1.5 h-1.5 rounded-full ${dot} shrink-0`}></span>}
      <span>{String(value).replace(/_/g, ' ')}</span>
    </span>
  )
}
