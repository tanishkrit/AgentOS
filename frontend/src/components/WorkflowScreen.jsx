import { useState, useRef, useEffect, useCallback } from 'react'
import TaskNode from './TaskNode'
import LogStream from './LogStream'
import ApprovalModal from './ApprovalModal'
import './WorkflowScreen.css'

export default function WorkflowScreen({
  goal,
  tasks,
  logs,
  workflowStatus,
  planApprovalPending,
  approvalRequest,
  createdFiles = [],
  screenFrame = null,
  cursorPos = { cx: 0, cy: 0, sw: 1, sh: 1 },
  onBack,
  onRespondApproval,
  onPlanApproval,
}) {
  const [activeTab, setActiveTab] = useState('live')
  const [selectedTask, setSelectedTask] = useState(null)
  const [liveExpanded, setLiveExpanded] = useState(false)
  const canvasSvgRef = useRef(null)
  const nodesRef = useRef({})

  // Auto-select the last task when completed/failed to show output
  useEffect(() => {
    if ((workflowStatus === 'completed' || workflowStatus === 'failed') && tasks.length > 0) {
      setSelectedTask(tasks[tasks.length - 1])
      setActiveTab('details')
    }
  }, [workflowStatus, tasks])

  const isPlanning = tasks.length === 0
  const completedCount = tasks.filter(t => t.status === 'completed').length
  const failedCount = tasks.filter(t => t.status === 'failed').length

  const badgeClass =
    workflowStatus === 'running' ? 'badge-running' :
    workflowStatus === 'completed' ? 'badge-completed' :
    workflowStatus === 'failed' ? 'badge-failed' : ''

  const badgeText =
    workflowStatus === 'planning' ? 'Planning...' :
    workflowStatus === 'awaiting-approval' ? 'Awaiting Approval' :
    workflowStatus === 'running' ? 'Running' :
    workflowStatus === 'completed' ? 'Completed' : 'Failed'

  // ── Render Sub-Node Icon helper ──────────────────────────────
  const renderSubNodeIcon = (icon) => {
    switch (icon) {
      case 'gemini':
        return (
          <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor" style={{ color: '#a78bfa' }}>
            <path d="M12 2a1 1 0 0 1 .897.553L14.71 6.18l3.628 1.814a1 1 0 0 1 0 1.788l-3.628 1.814-1.813 3.627a1 1 0 0 1-1.79 0L9.29 11.6l-3.628-1.814a1 1 0 0 1 0-1.788L9.29 6.18l1.813-3.627A1 1 0 0 1 12 2z"></path>
          </svg>
        )
      case 'database':
        return (
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#f472b6" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
            <ellipse cx="12" cy="5" rx="9" ry="3"></ellipse>
            <path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5"></path>
            <path d="M3 12c0 1.66 4 3 9 3s9-1.34 9-3"></path>
          </svg>
        )
      case 'search':
        return (
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#34d399" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="11" cy="11" r="8"></circle>
            <line x1="21" y1="21" x2="16.65" y2="16.65"></line>
          </svg>
        )
      case 'web':
        return (
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#34d399" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="12" cy="12" r="10"></circle>
            <line x1="2" y1="12" x2="22" y2="12"></line>
            <path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"></path>
          </svg>
        )
      case 'desktop':
        return (
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#34d399" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
            <rect x="2" y="3" width="20" height="14" rx="2" ry="2"></rect>
            <line x1="8" y1="21" x2="16" y2="21"></line>
            <line x1="12" y1="17" x2="12" y2="21"></line>
          </svg>
        )
      case 'mail':
        return (
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#34d399" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
            <path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"></path>
            <polyline points="22,6 12,13 2,6"></polyline>
          </svg>
        )
      default:
        return (
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#cbd5e1" strokeWidth="2.5">
            <circle cx="12" cy="12" r="10"></circle>
          </svg>
        )
    }
  }

  // ── Draw SVG connectors ──────────────────────────────────────
  const drawConnectors = useCallback(() => {
    const svg = canvasSvgRef.current
    if (!svg) return
    svg.innerHTML = ''

    const svgRect = svg.getBoundingClientRect()

    // Helper to draw curved connector to sub-node
    const drawSubConnector = (fromPortEl, toEl, type) => {
      const toPortEl = toEl.querySelector('.port-input')
      if (!fromPortEl || !toPortEl) return

      const fromRect = fromPortEl.getBoundingClientRect()
      const toRect = toPortEl.getBoundingClientRect()

      const x1 = fromRect.left + fromRect.width / 2 - svgRect.left
      const y1 = fromRect.top + fromRect.height / 2 - svgRect.top
      const x2 = toRect.left + toRect.width / 2 - svgRect.left
      const y2 = toRect.top + toRect.height / 2 - svgRect.top
      const midY = (y1 + y2) / 2

      const path = document.createElementNS('http://www.w3.org/2000/svg', 'path')
      path.setAttribute('d', `M ${x1} ${y1} C ${x1} ${midY}, ${x2} ${midY}, ${x2} ${y2}`)
      path.setAttribute('class', `connector-line sub-connector type-${type}`)
      svg.appendChild(path)
    }

    tasks.forEach((task) => {
      const toEl = nodesRef.current[task.id]
      if (!toEl) return

      // Draw main workflow connections (Horizontal bezier)
      task.depends_on.forEach((depId) => {
        const fromEl = nodesRef.current[depId]
        if (!fromEl) return

        const fromPort = fromEl.querySelector('.port-output')
        const toPort = toEl.querySelector('.port-input')

        if (fromPort && toPort) {
          const fromRect = fromPort.getBoundingClientRect()
          const toRect = toPort.getBoundingClientRect()

          const x1 = fromRect.left + fromRect.width / 2 - svgRect.left
          const y1 = fromRect.top + fromRect.height / 2 - svgRect.top
          const x2 = toRect.left + toRect.width / 2 - svgRect.left
          const y2 = toRect.top + toRect.height / 2 - svgRect.top
          
          const midX = (x1 + x2) / 2

          const path = document.createElementNS('http://www.w3.org/2000/svg', 'path')
          path.setAttribute('d', `M ${x1} ${y1} C ${midX} ${y1}, ${midX} ${y2}, ${x2} ${y2}`)

          const depTask = tasks.find(t => t.id === depId)
          let className = 'connector-line'
          if (depTask && depTask.status === 'completed') className += ' completed'
          else if (task.status === 'running' || task.status === 'thinking') className += ' active'
          path.setAttribute('class', className)

          svg.appendChild(path)
        }
      })

      // Draw sub-node connections (Vertical curves)
      const modelEl = nodesRef.current[`${task.id}_model`]
      const modelPort = toEl.querySelector('.port-model')
      if (modelEl && modelPort) {
        drawSubConnector(modelPort, modelEl, 'model')
      }

      const memoryEl = nodesRef.current[`${task.id}_memory`]
      const memoryPort = toEl.querySelector('.port-memory')
      if (memoryEl && memoryPort) {
        drawSubConnector(memoryPort, memoryEl, 'memory')
      }

      const toolPort = toEl.querySelector('.port-tool')
      const toolEl = nodesRef.current[`${task.id}_tool_ddg`] ||
                    nodesRef.current[`${task.id}_tool_playwright`] ||
                    nodesRef.current[`${task.id}_tool_pyautogui`] ||
                    nodesRef.current[`${task.id}_tool_smtp`]
      if (toolEl && toolPort) {
        drawSubConnector(toolPort, toolEl, 'tool')
      }
    })
  }, [tasks])

  useEffect(() => {
    const timer = setTimeout(drawConnectors, 250) // More delay to ensure refs are sized
    return () => clearTimeout(timer)
  }, [tasks, drawConnectors])

  // ── Register node refs ─────────────────────────────────────
  const setNodeRef = useCallback((id, el) => {
    nodesRef.current[id] = el
  }, [])

  return (
    <div className="workflow-screen">
      {/* ── Top Bar ───────────────────────────────────────── */}
      <div className="topbar">
        <div className="topbar-left">
          <button className="btn-icon" onClick={onBack} title="Back to prompt">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M19 12H5M12 19l-7-7 7-7"/>
            </svg>
          </button>
          <div className="topbar-title">
            <h2>{goal.length > 50 ? goal.slice(0, 50) + '...' : goal}</h2>
            <span className={`topbar-badge ${badgeClass}`}>{badgeText}</span>
          </div>
        </div>
        <div className="topbar-stats">
          <div className="stat"><span className="stat-value">{tasks.length}</span><span className="stat-label">Tasks</span></div>
          <div className="stat"><span className="stat-value">{completedCount}</span><span className="stat-label">Done</span></div>
          <div className="stat"><span className="stat-value">{failedCount}</span><span className="stat-label">Failed</span></div>
        </div>
      </div>

      {/* ── Main Body ─────────────────────────────────────── */}
      <div className="workflow-body">
        {/* Left: Canvas */}
        <div className="canvas-panel">
          <div className="canvas-area">
            {isPlanning && (
              <div className="thinking-indicator">
                <div className="thinking-brain">
                  <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="#8B5CF6" strokeWidth="1.5">
                    <path d="M12 2a7 7 0 0 0-7 7c0 2.38 1.19 4.47 3 5.74V17a2 2 0 0 0 2 2h4a2 2 0 0 0 2-2v-2.26c1.81-1.27 3-3.36 3-5.74a7 7 0 0 0-7-7z"/>
                    <line x1="9" y1="21" x2="15" y2="21"/>
                  </svg>
                </div>
                <span className="thinking-text">AI is decomposing goal into autonomous workflow...</span>
                <div className="thinking-dots"><span/><span/><span/></div>
              </div>
            )}

            <svg ref={canvasSvgRef} className="canvas-svg" />

            <div className="nodes-container">
              {tasks.map((task, i) => {
                const subNodes = []
                
                // Chat model sub-node
                subNodes.push({
                  id: `${task.id}_model`,
                  type: 'model',
                  label: 'Ollama LLM',
                  sublabel: 'Local AI Model',
                  icon: 'gemini'
                })

                // Blackboard Memory sub-node
                subNodes.push({
                  id: `${task.id}_memory`,
                  type: 'memory',
                  label: 'Blackboard Memory',
                  sublabel: 'InMemory DB',
                  icon: 'database'
                })

                // Specific agent tools sub-nodes
                if (task.agent_type === 'research') {
                  subNodes.push({
                    id: `${task.id}_tool_ddg`,
                    type: 'tool',
                    label: 'DuckDuckGo HTML',
                    sublabel: 'Search Engine',
                    icon: 'search'
                  })
                } else if (task.agent_type === 'browser') {
                  subNodes.push({
                    id: `${task.id}_tool_playwright`,
                    type: 'tool',
                    label: 'Playwright Browser',
                    sublabel: 'Web Automation',
                    icon: 'web'
                  })
                } else if (task.agent_type === 'desktop') {
                  subNodes.push({
                    id: `${task.id}_tool_pyautogui`,
                    type: 'tool',
                    label: 'PyAutoGUI OS',
                    sublabel: 'Desktop Automation',
                    icon: 'desktop'
                  })
                } else if (task.agent_type === 'email') {
                  subNodes.push({
                    id: `${task.id}_tool_smtp`,
                    type: 'tool',
                    label: 'SMTP/IMAP Service',
                    sublabel: 'Mail Server',
                    icon: 'mail'
                  })
                }

                return (
                  <div key={task.id} className="task-column">
                    <TaskNode
                      task={task}
                      index={i}
                      onClick={() => { setSelectedTask(task); setActiveTab('details') }}
                      ref={(el) => setNodeRef(task.id, el)}
                    />
                    
                    <div className="sub-nodes-container">
                      {subNodes.map((subNode) => (
                        <div
                          key={subNode.id}
                          className={`sub-node type-${subNode.type}`}
                          ref={(el) => setNodeRef(subNode.id, el)}
                        >
                          <div className="sub-node-icon-circle">
                            {renderSubNodeIcon(subNode.icon)}
                          </div>
                          <span className="sub-node-label">{subNode.label}</span>
                          <span className="sub-node-sublabel">{subNode.sublabel}</span>
                          <div className="port port-input" />
                        </div>
                      ))}
                    </div>
                  </div>
                )
              })}
            </div>
          </div>
        </div>

        {/* Right: Execution Panel */}
        <div className="exec-panel">
          <div className="exec-tabs">
            <button className={`exec-tab ${activeTab === 'live' ? 'active' : ''}`} onClick={() => setActiveTab('live')}>
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="2" y="3" width="20" height="14" rx="2" ry="2"/><line x1="8" y1="21" x2="16" y2="21"/><line x1="12" y1="17" x2="12" y2="21"/></svg>
              Live View
              {screenFrame && <span className="live-dot-indicator" />}
            </button>
            <button className={`exec-tab ${activeTab === 'logs' ? 'active' : ''}`} onClick={() => setActiveTab('logs')}>
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>
              Live Logs
            </button>
            <button className={`exec-tab ${activeTab === 'details' ? 'active' : ''}`} onClick={() => setActiveTab('details')}>
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>
              Task Details
            </button>
          </div>

          {activeTab === 'live' && (
            <div className={`live-view-panel ${liveExpanded ? 'expanded' : ''}`}>
              <div className="live-view-header">
                <div className="live-badge">
                  <span className="live-pulse" />
                  <span>LIVE</span>
                </div>
                <div className="live-actions">
                  <button
                    className="btn-icon-sm"
                    onClick={() => {
                      if (window.pywebview && window.pywebview.api) {
                        window.pywebview.api.toggle_screen_stream()
                      }
                    }}
                    title="Toggle stream"
                  >
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <circle cx="12" cy="12" r="10"/>
                      {screenFrame
                        ? <rect x="9" y="9" width="6" height="6" fill="currentColor"/>
                        : <polygon points="10,8 16,12 10,16" fill="currentColor"/>
                      }
                    </svg>
                  </button>
                  <button
                    className="btn-icon-sm"
                    onClick={() => setLiveExpanded(e => !e)}
                    title={liveExpanded ? 'Collapse' : 'Expand'}
                  >
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      {liveExpanded ? (
                        <><polyline points="4 14 10 14 10 20"/><polyline points="20 10 14 10 14 4"/><line x1="14" y1="10" x2="21" y2="3"/><line x1="3" y1="21" x2="10" y2="14"/></>
                      ) : (
                        <><polyline points="15 3 21 3 21 9"/><polyline points="9 21 3 21 3 15"/><line x1="21" y1="3" x2="14" y2="10"/><line x1="3" y1="21" x2="10" y2="14"/></>
                      )}
                    </svg>
                  </button>
                </div>
              </div>
              <div className="live-view-frame-wrapper">
                {screenFrame ? (
                  <>
                    <img
                      className="live-view-frame"
                      src={`data:image/jpeg;base64,${screenFrame}`}
                      alt="Live desktop view"
                      draggable={false}
                    />
                    {/* Cursor overlay */}
                    <div
                      className="live-cursor-dot"
                      style={{
                        left: `${(cursorPos.cx / cursorPos.sw) * 100}%`,
                        top: `${(cursorPos.cy / cursorPos.sh) * 100}%`,
                      }}
                    />
                  </>
                ) : (
                  <div className="live-view-placeholder">
                    <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="rgba(255,255,255,0.15)" strokeWidth="1.5">
                      <rect x="2" y="3" width="20" height="14" rx="2" ry="2"/>
                      <line x1="8" y1="21" x2="16" y2="21"/>
                      <line x1="12" y1="17" x2="12" y2="21"/>
                    </svg>
                    <p>Live screen feed will appear here when the workflow is running</p>
                    <span className="live-hint">The agent's desktop actions are streamed in real-time</span>
                  </div>
                )}
              </div>
            </div>
          )}

          {activeTab === 'logs' && <LogStream logs={logs} />}

          {activeTab === 'details' && (
            <div className="detail-panel">
              {!selectedTask ? (
                <div className="detail-empty">
                  <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="rgba(255,255,255,0.2)" strokeWidth="1.5">
                    <circle cx="12" cy="12" r="10"/><path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"/><line x1="12" y1="17" x2="12.01" y2="17"/>
                  </svg>
                  <p>Click a task node to see details</p>
                </div>
              ) : (
                <div className="detail-view">
                  <h3>{selectedTask.description}</h3>
                  <div className="detail-meta">
                    <span className={`detail-agent badge-${selectedTask.agent_type}`}>{selectedTask.agent_type}</span>
                    <span className={`detail-status status-${selectedTask.status}`}>{selectedTask.status}</span>
                  </div>
                  
                  <div className="detail-block">
                    <h4>Parameters</h4>
                    <pre>{JSON.stringify(selectedTask.parameters || {}, null, 2)}</pre>
                  </div>
                  
                  {selectedTask.result && (
                    <div className="detail-block">
                      <h4>Output / Extracted Data</h4>
                      
                      {selectedTask.result.summary && (
                        <div className="result-summary-box">
                          {selectedTask.result.summary}
                        </div>
                      )}

                      {/* Display file path if created */}
                      {selectedTask.result.filepath && (
                        <div className="created-file-badge">
                          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#10B981" strokeWidth="2">
                            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                            <polyline points="14 2 14 8 20 8"/>
                          </svg>
                          <span>📂 Created: {selectedTask.result.filepath}</span>
                        </div>
                      )}

                      {/* Display regex-extracted contacts if present */}
                      {selectedTask.result.extracted && (
                        <div className="extracted-contacts-section">
                          {selectedTask.result.extracted.emails && selectedTask.result.extracted.emails.length > 0 && (
                            <div className="extracted-list-block">
                              <h5>Extracted Emails ({selectedTask.result.extracted.emails.length})</h5>
                              <table className="extracted-table">
                                <thead>
                                  <tr><th>Email Address</th></tr>
                                </thead>
                                <tbody>
                                  {selectedTask.result.extracted.emails.map((email, idx) => (
                                    <tr key={idx}><td>{email}</td></tr>
                                  ))}
                                </tbody>
                              </table>
                            </div>
                          )}

                          {selectedTask.result.extracted.phones && selectedTask.result.extracted.phones.length > 0 && (
                            <div className="extracted-list-block">
                              <h5>Extracted Phone Numbers ({selectedTask.result.extracted.phones.length})</h5>
                              <table className="extracted-table">
                                <thead>
                                  <tr><th>Phone Number</th></tr>
                                </thead>
                                <tbody>
                                  {selectedTask.result.extracted.phones.map((phone, idx) => (
                                    <tr key={idx}><td>{phone}</td></tr>
                                  ))}
                                </tbody>
                              </table>
                            </div>
                          )}
                        </div>
                      )}

                      {/* Display scraped website source logs if present */}
                      {selectedTask.result.data && selectedTask.result.data.length > 0 && (
                        <div className="scraped-sources-section">
                          <h5>Scraped Online Sources ({selectedTask.result.data.length})</h5>
                          <div className="sources-list">
                            {selectedTask.result.data.map((source, idx) => (
                              <div key={idx} className="source-item-card">
                                <div className="source-title-row">
                                  <span className="source-badge">{source.type || 'web'}</span>
                                  <a href={source.source} target="_blank" rel="noopener noreferrer" className="source-link">
                                    {source.title || (source.source && source.source.length > 40 ? source.source.slice(0, 40) + '...' : source.source) || `Source #${idx+1}`}
                                  </a>
                                </div>
                                {source.snippet && <p className="source-snippet">"{source.snippet}"</p>}
                              </div>
                            ))}
                          </div>
                        </div>
                      )}

                      {/* Fallback print if no structured keys exist */}
                      {!selectedTask.result.extracted && !selectedTask.result.data && !selectedTask.result.filepath && (
                        <pre>{JSON.stringify(selectedTask.result, null, 2)}</pre>
                      )}
                    </div>
                  )}

                  {/* Show created files for this task */}
                  {createdFiles.length > 0 && (workflowStatus === 'completed' || workflowStatus === 'failed') && (
                    <div className="detail-block created-files-block">
                      <h4>📂 Files Created During Workflow</h4>
                      <div className="created-files-list">
                        {createdFiles.map((file, idx) => (
                          <div key={idx} className="created-file-item">
                            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#10B981" strokeWidth="2">
                              <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                              <polyline points="14 2 14 8 20 8"/>
                            </svg>
                            <span>{file}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* ── Plan Approval Bar ─────────────────────────────── */}
      {planApprovalPending && (
        <div className="plan-approval-bar">
          <div className="plan-approval-content">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#F59E0B" strokeWidth="2">
              <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/>
            </svg>
            <span>Review the workflow above. Ready to execute?</span>
          </div>
          <div className="plan-approval-actions">
            <button className="btn-deny" onClick={() => onPlanApproval(false)}>Cancel</button>
            <button className="btn-approve" onClick={() => onPlanApproval(true)}>
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="20 6 9 17 4 12"/></svg>
              Run Workflow
            </button>
          </div>
        </div>
      )}

      {/* ── Approval Modal ────────────────────────────────── */}
      {approvalRequest && (
        <ApprovalModal
          description={approvalRequest.description}
          onApprove={() => onRespondApproval(true)}
          onDeny={() => onRespondApproval(false)}
        />
      )}
    </div>
  )
}
