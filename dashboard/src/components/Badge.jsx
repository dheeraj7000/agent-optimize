/** Status / priority / confidence badges. */
const styles = {
  // Status
  pending: 'bg-yellow-100 text-yellow-700',
  accepted: 'bg-blue-100 text-blue-700',
  rejected: 'bg-red-100 text-red-700',
  replaying: 'bg-purple-100 text-purple-700',
  validated: 'bg-green-100 text-green-700',
  deployed: 'bg-emerald-100 text-emerald-700',
  verified: 'bg-green-200 text-green-800',
  rolled_back: 'bg-red-200 text-red-800',
  // Priority
  critical: 'bg-red-100 text-red-700',
  high: 'bg-orange-100 text-orange-700',
  medium: 'bg-yellow-100 text-yellow-700',
  low: 'bg-gray-100 text-gray-600',
  // Confidence
  // high: already mapped
  // Verdicts
  pass: 'bg-green-100 text-green-700',
  fail: 'bg-red-100 text-red-700',
  warn: 'bg-amber-100 text-amber-700',
  skip: 'bg-gray-100 text-gray-500',
  // Autopilot
  off: 'bg-gray-100 text-gray-500',
  suggest: 'bg-blue-100 text-blue-700',
  supervised: 'bg-yellow-100 text-yellow-700',
  autonomous: 'bg-green-100 text-green-700',
  // Canary
  running: 'bg-blue-100 text-blue-700',
  healthy: 'bg-green-100 text-green-700',
  degraded: 'bg-amber-100 text-amber-700',
  regressed: 'bg-red-100 text-red-700',
  completed: 'bg-green-200 text-green-800',
}

export default function Badge({ value, className = '' }) {
  if (!value) return null
  const s = styles[value] || 'bg-gray-100 text-gray-600'
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${s} ${className}`}>
      {value.replace(/_/g, ' ')}
    </span>
  )
}
