const tones = {
  pending: 'badge-neutral', accepted: 'badge-info', rejected: 'badge-danger',
  replaying: 'badge-info', validated: 'badge-success', deployed: 'badge-success',
  verified: 'badge-success', rolled_back: 'badge-danger', critical: 'badge-danger',
  high: 'badge-warning', medium: 'badge-neutral', low: 'badge-neutral',
  pass: 'badge-success', fail: 'badge-danger', warn: 'badge-warning', skip: 'badge-neutral',
  off: 'badge-neutral', suggest: 'badge-info', supervised: 'badge-warning',
  autonomous: 'badge-success', running: 'badge-info', healthy: 'badge-success',
  degraded: 'badge-warning', regressed: 'badge-danger', completed: 'badge-success',
}

export default function Badge({ value, className = '' }) {
  if (!value) return null
  const tone = tones[String(value).toLowerCase()] || 'badge-neutral'
  return <span className={`status-badge ${tone} ${className}`}>{String(value).replace(/_/g, ' ')}</span>
}
