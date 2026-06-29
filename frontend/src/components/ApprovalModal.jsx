import './ApprovalModal.css'

export default function ApprovalModal({ description, onApprove, onDeny }) {
  return (
    <div className="approval-overlay">
      <div className="approval-modal">
        <div className="approval-icon">
          <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="#F59E0B" strokeWidth="1.5">
            <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
          </svg>
        </div>
        <h3 className="approval-title">Approval Required</h3>
        <p className="approval-desc">{description}</p>
        <div className="approval-actions">
          <button className="btn-deny" onClick={onDeny}>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
            </svg>
            Deny
          </button>
          <button className="btn-approve" onClick={onApprove}>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <polyline points="20 6 9 17 4 12"/>
            </svg>
            Approve
          </button>
        </div>
      </div>
    </div>
  )
}
