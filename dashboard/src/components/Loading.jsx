export function Loading({ label = 'Loading workspace data…' }) {
  return (
    <div className="loading-state" role="status" aria-live="polite">
      <span className="loading-indicator" aria-hidden="true" />
      <span>{label}</span>
    </div>
  )
}

export function ErrorMessage({ message }) {
  return (
    <div className="error-message" role="alert">
      <span className="error-indicator" aria-hidden="true" />
      <span>{message || 'An unexpected error occurred'}</span>
    </div>
  )
}
