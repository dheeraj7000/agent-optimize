const tones = {
  green: 'metric-icon-green',
  blue: 'metric-icon-blue',
  cyan: 'metric-icon-blue',
  amber: 'metric-icon-amber',
  red: 'metric-icon-red',
  gray: 'metric-icon-gray',
}

export default function StatCard({ label, value, sub, icon: Icon, color = 'green', featured = false }) {
  return (
    <article className={`metric-card ${featured ? 'metric-card-featured' : ''}`}>
      <div className="metric-card-top">
        <p className="metric-label">{label}</p>
        {Icon && <span className={`metric-icon ${tones[color] || tones.green}`}><Icon size={16} strokeWidth={1.9} /></span>}
      </div>
      <p className="metric-value">{value}</p>
      {sub && <p className="metric-sub">{sub}</p>}
    </article>
  )
}
