import React from 'react'
import { createRoot } from 'react-dom/client'
import App from './App.jsx'
import { initApi } from './api.js'
import { initAuth } from './auth.js'
import './styles.css'

async function boot() {
  const root = createRoot(document.getElementById('root'))
  try {
    const res = await fetch('/config.json', { cache: 'no-store' })
    const config = await res.json()
    if (!config.apiUrl || config.apiUrl.startsWith('REPLACED')) {
      throw new Error('config.json has not been generated yet. Run scripts/deploy.py first.')
    }
    initAuth(config)
    initApi(config)
    root.render(<App />)
  } catch (e) {
    root.render(<div className="boot-error"><h2>Configuration error</h2><p>{e.message}</p></div>)
  }
}

boot()
