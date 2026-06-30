import { forwardRef } from 'react'
import './TaskNode.css'

const TaskNode = forwardRef(function TaskNode({ task, index, onClick }, ref) {
  const getAgentTitle = (type) => {
    switch (type) {
      case 'research': return 'Research Agent'
      case 'browser': return 'Browser Agent'
      case 'desktop': return 'Desktop Agent'
      case 'email': return 'Email Agent'
      case 'presentation': return 'Presentation Agent'
      case 'verification': return 'Verification Agent'
      default: return 'AI Agent'
    }
  }

  const getAgentIcon = (type) => {
    switch (type) {
      case 'research':
        return (
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="11" cy="11" r="8"></circle>
            <line x1="21" y1="21" x2="16.65" y2="16.65"></line>
          </svg>
        )
      case 'browser':
        return (
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="12" cy="12" r="10"></circle>
            <line x1="2" y1="12" x2="22" y2="12"></line>
            <path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"></path>
          </svg>
        )
      case 'desktop':
        return (
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
            <rect x="2" y="3" width="20" height="14" rx="2" ry="2"></rect>
            <line x1="8" y1="21" x2="16" y2="21"></line>
            <line x1="12" y1="17" x2="12" y2="21"></line>
          </svg>
        )
      case 'email':
        return (
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
            <path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"></path>
            <polyline points="22,6 12,13 2,6"></polyline>
          </svg>
        )
      case 'presentation':
        return (
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
            <rect x="2" y="3" width="20" height="14" rx="2" ry="2"></rect>
            <line x1="8" y1="21" x2="16" y2="21"></line>
            <line x1="12" y1="17" x2="12" y2="21"></line>
          </svg>
        )
      case 'verification':
        return (
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
            <path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2"></path>
            <rect x="8" y="2" width="8" height="4" rx="1" ry="1"></rect>
            <polyline points="9 14 11 16 15 12"></polyline>
          </svg>
        )
      default:
        return (
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
            <rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect>
            <line x1="9" y1="3" x2="9" y2="21"></line>
          </svg>
        )
    }
  }

  // Determine if agent uses specialized tools
  const hasTool = ['research', 'browser', 'desktop', 'email', 'presentation', 'verification'].includes(task.agent_type)

  return (
    <div
      ref={ref}
      className={`task-node ${task.status}`}
      style={{ animationDelay: `${index * 0.1}s` }}
      onClick={onClick}
    >
      {/* Input / Output ports */}
      <div className="port port-input" title="Input Connection"></div>
      <div className="port port-output" title="Output Connection"></div>
      
      {/* Bottom dependency ports */}
      <div className="ports-bottom">
        <div className="port-bottom port-model" title="Chat Model"></div>
        <div className="port-bottom port-memory" title="Memory"></div>
        {hasTool && <div className="port-bottom port-tool" title="Tool"></div>}
      </div>

      <div className="node-body">
        <div className={`node-icon-wrapper agent-${task.agent_type}`}>
          {getAgentIcon(task.agent_type)}
        </div>
        <div className="node-content">
          <div className="node-title-row">
            <span className="node-title">{getAgentTitle(task.agent_type)}</span>
            <span className="node-status-icon">
              <StatusIndicator status={task.status} />
            </span>
          </div>
          <div className="node-description" title={task.description}>
            {task.description.length > 55 ? task.description.slice(0, 52) + '...' : task.description}
          </div>
        </div>
      </div>
      
      <div className="node-footer">
        <span className="node-id-badge">{task.id}</span>
        {task.result && task.result.summary && (
          <span className="node-summary-text" title={task.result.summary}>
            {task.result.summary.length > 30 ? task.result.summary.slice(0, 27) + '...' : task.result.summary}
          </span>
        )}
      </div>
    </div>
  )
})

function StatusIndicator({ status }) {
  switch (status) {
    case 'pending':
      return <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="var(--text-muted)" strokeWidth="2.5"><circle cx="12" cy="12" r="10"/></svg>
    case 'thinking':
      return <div className="spinner purple" />
    case 'running':
      return <div className="spinner" />
    case 'completed':
      return <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="var(--accent-green)" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round"><polyline points="20 6 9 17 4 12"/></svg>
    case 'failed':
      return <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="var(--accent-red)" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
    case 'waiting-approval':
      return <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="var(--accent-amber)" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>
    default:
      return null
  }
}

export default TaskNode
