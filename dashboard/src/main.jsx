import { BrowserRouter, useLocation } from 'react-router-dom'
import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'
import './index.css'

function RouteAwareBody() {
  const location = useLocation()
  React.useEffect(() => {
    const isMarketing = location.pathname === '/'
    document.body.classList.toggle('marketing-body', isMarketing)
    document.title = isMarketing ? 'AgentOptimize — Make every agent run count' : 'AgentOptimize — AI Agent FinOps'
    return () => document.body.classList.remove('marketing-body')
  }, [location.pathname])
  return <App />
}

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <BrowserRouter>
      <RouteAwareBody />
    </BrowserRouter>
  </React.StrictMode>,
)
