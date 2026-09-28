import { useEffect, useState } from 'react'
import { ShieldAlert, ShieldCheck, X } from 'lucide-react'
import { api, isAuthConfigured } from '../lib/api'

/**
 * Security posture banner driven by the backend's /status auth_required flag.
 *
 * Shows only when the server reports authentication is disabled AND no API key
 * is configured locally. Warns operators before they expose the deployment.
 * Dismissal persists per browser (sessionStorage) so it reappears per session.
 */
export default function SecurityBanner() {
  const [status, setStatus] = useState(null)
  const [dismissed, setDismissed] = useState(() => {
    try {
      return sessionStorage.getItem('ao_banner_dismissed') === '1'
    } catch {
      return false
    }
  })

  useEffect(() => {
    api.status()
      .then(setStatus)
      .catch(() => setStatus(null))
  }, [])

  const authRequired = status?.auth_required === true
  const hasKey = isAuthConfigured()
  const visible = status && !authRequired && !hasKey && !dismissed
  if (!visible) return null

  const dismiss = () => {
    setDismissed(true)
    try {
      sessionStorage.setItem('ao_banner_dismissed', '1')
    } catch {
      // ignore storage errors
    }
  }

  return (
    <div className="auth-banner" role="alert">
      <span className="auth-banner-icon"><ShieldAlert size={15} /></span>
      <div className="auth-banner-copy">
        <strong>API is running without authentication.</strong>
        <span>
          Any visitor can write telemetry or change settings. Set{' '}
          <code>AGENTOPTIMIZE_API_KEY_REQUIRED=true</code>, then generate a key with{' '}
          <code>agent-optimize create-key --tenant &lt;id&gt;</code> and open this dashboard as{' '}
          <code>/?key=YOUR_KEY</code>.
        </span>
      </div>
      <span className="auth-banner-ok"><ShieldCheck size={13} /> secure when auth is on</span>
      <button type="button" className="auth-banner-close" onClick={dismiss} aria-label="Dismiss security banner">
        <X size={14} />
      </button>
    </div>
  )
}
