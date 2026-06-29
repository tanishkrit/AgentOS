import { useEffect, useRef } from 'react'
import './LogStream.css'

export default function LogStream({ logs }) {
  const containerRef = useRef(null)

  // Auto-scroll to bottom on new log
  useEffect(() => {
    if (containerRef.current) {
      containerRef.current.scrollTop = containerRef.current.scrollHeight
    }
  }, [logs])

  return (
    <div className="log-stream" ref={containerRef}>
      {logs.length === 0 && (
        <div className="log-entry">
          <span className="log-time">--:--:--</span>
          <span className="log-badge system">SYSTEM</span>
          <span className="log-text">Waiting for workflow to start...</span>
        </div>
      )}
      {logs.map((log) => (
        <div key={log.id} className={`log-entry log-${log.level}`}>
          <span className="log-time">{log.time}</span>
          <span className={`log-badge ${log.level}`}>{log.level.toUpperCase()}</span>
          <span className="log-text">{log.message}</span>
        </div>
      ))}
    </div>
  )
}
