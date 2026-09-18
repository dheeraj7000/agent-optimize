/** API client for AgentOptimize backend. */

const BASE = ''  // Same origin in production; proxied in dev

async function request(path, options = {}) {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...options.headers },
    ...options,
  })
  if (!res.ok) {
    const text = await res.text()
    throw new Error(`${res.status}: ${text}`)
  }
  return res.json()
}

export const api = {
  // Health
  health: () => request('/health'),
  status: () => request('/status'),

  // Dashboard
  opportunities: (days = 7) => request(`/api/dashboard/opportunities?window_days=${days}`),
  stats: (hours = 168) => request(`/api/dashboard/stats?window_hours=${hours}`),
  runs: (limit = 50) => request(`/api/dashboard/runs?limit=${limit}`),

  // Traces
  traces: (params = {}) => {
    const qs = new URLSearchParams(params).toString()
    return request(`/api/traces?${qs}`)
  },
  trace: (id) => request(`/api/traces/${id}`),
  traceCost: (id) => request(`/api/traces/${id}/cost`),
  traceWaste: (id) => request(`/api/traces/${id}/waste`),

  // Recommendations
  recommendations: (params = {}) => {
    const qs = new URLSearchParams(params).toString()
    return request(`/api/recommendations?${qs}`)
  },
  recommendation: (id) => request(`/api/recommendations/${id}`),
  recommendationStats: () => request('/api/recommendations/stats'),
  generateRecommendations: (body = {}) =>
    request('/api/recommendations/generate', { method: 'POST', body: JSON.stringify(body) }),
  transitionRecommendation: (id, action, body = {}) =>
    request(`/api/recommendations/${id}/${action}`, { method: 'POST', body: JSON.stringify(body) }),

  // Validation
  evaluators: () => request('/api/validation/evaluators'),
  proofs: () => request('/api/validation/proofs'),
  canaries: () => request('/api/validation/canaries'),

  // Autopilot
  autopilotStatus: () => request('/api/autopilot/status'),
  setMode: (mode) => request('/api/autopilot/mode', { method: 'POST', body: JSON.stringify({ mode }) }),
  routingStats: () => request('/api/autopilot/route/stats'),
  verifyStats: () => request('/api/autopilot/verify/stats'),
  recoveryStats: () => request('/api/autopilot/recover/stats'),
  decisions: (limit = 20) => request(`/api/autopilot/decisions?limit=${limit}`),
  policies: () => request('/api/autopilot/policies'),
}
