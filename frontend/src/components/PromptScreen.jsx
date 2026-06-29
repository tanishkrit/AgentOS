import { useState, useEffect, useCallback } from 'react'
import './PromptScreen.css'

export default function PromptScreen({ approvalMode, onApprovalModeChange, onSubmit }) {
  const [goal, setGoal] = useState('')
  const [showSettings, setShowSettings] = useState(false)
  const [settingsBaseUrl, setSettingsBaseUrl] = useState('http://localhost:11434')
  const [settingsModel, setSettingsModel] = useState('')
  const [localModels, setLocalModels] = useState([])
  const [ollamaStatus, setOllamaStatus] = useState('unknown') // unknown | checking | online | offline
  const [saveStatus, setSaveStatus] = useState(null) // null | 'saving' | 'saved' | 'error'

  const handleSubmit = () => {
    if (goal.trim()) onSubmit(goal.trim())
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSubmit()
    }
  }

  // ── Load settings when panel opens ──────────────────────────────
  const loadSettings = useCallback(async () => {
    if (!window.pywebview?.api) return
    try {
      setOllamaStatus('checking')
      const config = await window.pywebview.api.get_llm_config()
      setSettingsBaseUrl(config.base_url || 'http://localhost:11434')
      setSettingsModel(config.model || '')
      setOllamaStatus(config.available ? 'online' : 'offline')

      const models = await window.pywebview.api.list_local_models()
      setLocalModels(models || [])
    } catch (err) {
      console.error('Failed to load settings:', err)
      setOllamaStatus('offline')
    }
  }, [])

  useEffect(() => {
    if (showSettings) loadSettings()
  }, [showSettings, loadSettings])

  // ── Test connection ─────────────────────────────────────────────
  const handleTestConnection = async () => {
    setOllamaStatus('checking')
    try {
      if (window.pywebview?.api) {
        const result = await window.pywebview.api.save_llm_config(
          JSON.stringify({ base_url: settingsBaseUrl, model: settingsModel })
        )
        setOllamaStatus(result.available ? 'online' : 'offline')
        const models = await window.pywebview.api.list_local_models()
        setLocalModels(models || [])
      }
    } catch {
      setOllamaStatus('offline')
    }
  }

  // ── Save settings ──────────────────────────────────────────────
  const handleSaveSettings = async () => {
    setSaveStatus('saving')
    try {
      if (window.pywebview?.api) {
        const result = await window.pywebview.api.save_llm_config(
          JSON.stringify({ base_url: settingsBaseUrl, model: settingsModel })
        )
        setOllamaStatus(result.available ? 'online' : 'offline')
        setSaveStatus(result.success ? 'saved' : 'error')
      } else {
        setSaveStatus('saved')
      }
    } catch {
      setSaveStatus('error')
    }
    setTimeout(() => setSaveStatus(null), 2500)
  }

  const statusColors = {
    unknown: 'var(--text-muted)',
    checking: 'var(--accent-yellow, #F59E0B)',
    online: 'var(--accent-green)',
    offline: 'var(--accent-red, #EF4444)',
  }
  const statusLabels = {
    unknown: 'Unknown',
    checking: 'Checking...',
    online: 'Connected',
    offline: 'Offline',
  }

  return (
    <div className="prompt-screen">
      {/* Background orbs */}
      <div className="prompt-bg-orbs">
        <div className="orb orb-1" />
        <div className="orb orb-2" />
        <div className="orb orb-3" />
      </div>

      {/* Settings gear button */}
      <button className="btn-settings-gear" onClick={() => setShowSettings(true)} title="Settings">
        <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <circle cx="12" cy="12" r="3"/>
          <path d="M19.4 15a1.65 1.65 0 00.33 1.82l.06.06a2 2 0 010 2.83 2 2 0 01-2.83 0l-.06-.06a1.65 1.65 0 00-1.82-.33 1.65 1.65 0 00-1 1.51V21a2 2 0 01-2 2 2 2 0 01-2-2v-.09A1.65 1.65 0 009 19.4a1.65 1.65 0 00-1.82.33l-.06.06a2 2 0 01-2.83 0 2 2 0 010-2.83l.06-.06A1.65 1.65 0 004.68 15a1.65 1.65 0 00-1.51-1H3a2 2 0 01-2-2 2 2 0 012-2h.09A1.65 1.65 0 004.6 9a1.65 1.65 0 00-.33-1.82l-.06-.06a2 2 0 010-2.83 2 2 0 012.83 0l.06.06A1.65 1.65 0 009 4.68a1.65 1.65 0 001-1.51V3a2 2 0 012-2 2 2 0 012 2v.09a1.65 1.65 0 001 1.51 1.65 1.65 0 001.82-.33l.06-.06a2 2 0 012.83 0 2 2 0 010 2.83l-.06.06A1.65 1.65 0 0019.32 9a1.65 1.65 0 001.51 1H21a2 2 0 012 2 2 2 0 01-2 2h-.09a1.65 1.65 0 00-1.51 1z"/>
        </svg>
      </button>

      {/* Settings Modal Overlay */}
      {showSettings && (
        <div className="settings-overlay" onClick={(e) => {
          if (e.target === e.currentTarget) setShowSettings(false)
        }}>
          <div className="settings-modal">
            <div className="settings-modal-header">
              <h3>
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <circle cx="12" cy="12" r="3"/>
                  <path d="M19.4 15a1.65 1.65 0 00.33 1.82l.06.06a2 2 0 010 2.83 2 2 0 01-2.83 0l-.06-.06a1.65 1.65 0 00-1.82-.33 1.65 1.65 0 00-1 1.51V21a2 2 0 01-2 2 2 2 0 01-2-2v-.09A1.65 1.65 0 009 19.4a1.65 1.65 0 00-1.82.33l-.06.06a2 2 0 01-2.83 0 2 2 0 010-2.83l.06-.06A1.65 1.65 0 004.68 15a1.65 1.65 0 00-1.51-1H3a2 2 0 01-2-2 2 2 0 012-2h.09A1.65 1.65 0 004.6 9a1.65 1.65 0 00-.33-1.82l-.06-.06a2 2 0 010-2.83 2 2 0 012.83 0l.06.06A1.65 1.65 0 009 4.68a1.65 1.65 0 001-1.51V3a2 2 0 012-2 2 2 0 012 2v.09a1.65 1.65 0 001 1.51 1.65 1.65 0 001.82-.33l.06-.06a2 2 0 012.83 0 2 2 0 010 2.83l-.06.06A1.65 1.65 0 0019.32 9a1.65 1.65 0 001.51 1H21a2 2 0 012 2 2 2 0 01-2 2h-.09a1.65 1.65 0 00-1.51 1z"/>
                </svg>
                Local AI Settings
              </h3>
              <button className="btn-close-modal" onClick={() => setShowSettings(false)}>
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
                </svg>
              </button>
            </div>

            <div className="settings-modal-body">
              {/* Connection status */}
              <div className="settings-status-bar">
                <span className="settings-status-dot" style={{ background: statusColors[ollamaStatus] }} />
                <span>Ollama: {statusLabels[ollamaStatus]}</span>
              </div>

              {/* Base URL */}
              <div className="settings-field">
                <label>Ollama Server URL</label>
                <input
                  type="text"
                  value={settingsBaseUrl}
                  onChange={(e) => setSettingsBaseUrl(e.target.value)}
                  placeholder="http://localhost:11434"
                />
              </div>

              {/* Model selection */}
              <div className="settings-field">
                <label>Active Model</label>
                {localModels.length > 0 ? (
                  <select
                    value={settingsModel}
                    onChange={(e) => setSettingsModel(e.target.value)}
                  >
                    {localModels.map(m => (
                      <option key={m.name} value={m.name}>
                        {m.name} ({m.size})
                      </option>
                    ))}
                  </select>
                ) : (
                  <input
                    type="text"
                    value={settingsModel}
                    onChange={(e) => setSettingsModel(e.target.value)}
                    placeholder="e.g. qwen2.5:14b"
                  />
                )}
                <span className="settings-field-hint">
                  {localModels.length > 0
                    ? `${localModels.length} model${localModels.length > 1 ? 's' : ''} available locally`
                    : 'Type model name or connect to Ollama to see available models'}
                </span>
              </div>

              {/* Actions */}
              <div className="settings-actions">
                <button className="btn-test-connection" onClick={handleTestConnection}>
                  {ollamaStatus === 'checking' ? (
                    <><span className="spinner-sm" /> Testing...</>
                  ) : (
                    <>
                      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                        <path d="M22 11.08V12a10 10 0 11-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/>
                      </svg>
                      Test Connection
                    </>
                  )}
                </button>
                <button className="btn-save-settings" onClick={handleSaveSettings}>
                  {saveStatus === 'saving' ? (
                    <><span className="spinner-sm" /> Saving...</>
                  ) : saveStatus === 'saved' ? (
                    <>✅ Saved!</>
                  ) : saveStatus === 'error' ? (
                    <>❌ Error</>
                  ) : (
                    <>
                      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                        <path d="M19 21H5a2 2 0 01-2-2V5a2 2 0 012-2h11l5 5v11a2 2 0 01-2 2z"/>
                        <polyline points="17 21 17 13 7 13 7 21"/><polyline points="7 3 7 8 15 8"/>
                      </svg>
                      Save Settings
                    </>
                  )}
                </button>
              </div>

              <p className="settings-info-text">
                All AI processing runs 100% locally on your machine via Ollama.
                Download larger models with <code>ollama pull model_name</code> for better results.
              </p>
            </div>
          </div>
        </div>
      )}

      <div className="prompt-container">
        {/* Logo */}
        <div className="logo-section">
          <div className="logo-icon">
            <svg width="48" height="48" viewBox="0 0 48 48" fill="none">
              <circle cx="24" cy="24" r="22" stroke="url(#lg)" strokeWidth="2.5" fill="none"/>
              <circle cx="24" cy="24" r="8" fill="url(#lg)" opacity="0.8"/>
              <circle cx="24" cy="12" r="3" fill="#8B5CF6"/>
              <circle cx="34" cy="30" r="3" fill="#06B6D4"/>
              <circle cx="14" cy="30" r="3" fill="#10B981"/>
              <defs>
                <linearGradient id="lg" x1="0" y1="0" x2="48" y2="48">
                  <stop offset="0%" stopColor="#8B5CF6"/>
                  <stop offset="100%" stopColor="#06B6D4"/>
                </linearGradient>
              </defs>
            </svg>
          </div>
          <h1 className="logo-title">Agent<span className="logo-accent">OS</span></h1>
          <p className="logo-subtitle">Autonomous AI Workforce Operating System</p>
        </div>

        {/* Input */}
        <div className="input-section">
          <div className="input-wrapper">
            <div className="input-glow" />
            <textarea
              value={goal}
              onChange={(e) => setGoal(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Describe your goal... e.g., Research 10 AI startups and create a summary report"
              rows={3}
              autoFocus
            />
            <button
              className="btn-submit"
              onClick={handleSubmit}
              disabled={!goal.trim()}
            >
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M22 2L11 13M22 2l-7 20-4-9-9-4 20-7z"/>
              </svg>
              <span>Launch Agents</span>
            </button>
          </div>
        </div>

        {/* Settings */}
        <div className="settings-section">
          <div className="setting-card">
            <div className="setting-header">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
              </svg>
              <span>Approval Mode</span>
            </div>
            <div className="toggle-group">
              <button
                className={`toggle-btn ${approvalMode === 'manual' ? 'active' : ''}`}
                onClick={() => onApprovalModeChange('manual')}
              >
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/>
                </svg>
                Manual Review
              </button>
              <button
                className={`toggle-btn ${approvalMode === 'auto' ? 'active' : ''}`}
                onClick={() => onApprovalModeChange('auto')}
              >
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z"/>
                </svg>
                Auto-Approve
              </button>
            </div>
            <p className="setting-hint">
              {approvalMode === 'manual'
                ? 'Sensitive actions will require your confirmation before executing.'
                : 'All actions will execute automatically without pausing for approval.'}
            </p>
          </div>

          <div className="status-pill">
            <span className="status-dot" />
            <span>System Ready</span>
          </div>
        </div>
      </div>
    </div>
  )
}

