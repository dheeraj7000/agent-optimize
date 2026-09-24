export function Loading({ label = 'Analyzing telemetry…' }) {
  return (
    <div className="flex flex-col items-center justify-center py-16 gap-3">
      <div className="relative w-8 h-8">
        <div className="w-8 h-8 rounded-full border-2 border-slate-200"></div>
        <div className="absolute top-0 left-0 w-8 h-8 rounded-full border-2 border-emerald-500 border-t-transparent animate-spin"></div>
      </div>
      <span className="font-mono text-xs text-slate-400 tracking-tight">{label}</span>
    </div>
  )
}

export function ErrorMessage({ message }) {
  return (
    <div className="bg-rose-50/80 border border-rose-200/80 rounded-xl p-4 text-rose-800 text-sm font-sans flex items-center justify-between">
      <div className="flex items-center gap-2">
        <span className="w-2 h-2 rounded-full bg-rose-500"></span>
        <span className="font-medium">{message || 'An unexpected error occurred'}</span>
      </div>
      <span className="font-mono text-xs text-rose-400">check console</span>
    </div>
  )
}
