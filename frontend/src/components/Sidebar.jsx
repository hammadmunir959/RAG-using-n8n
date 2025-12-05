import { useState } from 'react'
import './Sidebar.css'

function Sidebar({
  documents = [],
  conversations = [],
  currentConversationId,
  onStartNewConversation,
  onConversationSelect,
  onUploadClick,
  onManageDocuments,
  onDeleteDocument,
  onDeleteConversation,
}) {
  const [isCollapsed, setIsCollapsed] = useState(false)

  return (
    <div className={`sidebar ${isCollapsed ? 'collapsed' : ''}`}>
      <div className="sidebar-header">
        <button
          className="toggle-btn"
          onClick={() => setIsCollapsed(!isCollapsed)}
          aria-label="Toggle sidebar"
        >
          {isCollapsed ? '→' : '←'}
        </button>
        {!isCollapsed && (
          <div className="sidebar-title">
            <h3>Document AI</h3>
          </div>
        )}
      </div>

      <div className="sidebar-content">
        {/* Primary Action */}
        <div className="sidebar-section">
          {!isCollapsed && <h4 className="section-title">Conversation</h4>}
          <button className="primary-btn" onClick={onStartNewConversation}>
            <span className="btn-icon">✨</span>
            {!isCollapsed && <span>Start new conversation</span>}
          </button>
        </div>

        {/* Documents */}
        <div className="sidebar-section">
          <div className="section-header">
            {!isCollapsed && <h4>Documents</h4>}
            {!isCollapsed && <span className="file-count">{documents.length}</span>}
          </div>
          <div className="docs-actions">
            <button className="nav-item" onClick={onUploadClick}>
              <span className="nav-icon">📤</span>
              {!isCollapsed && <span className="nav-text">Upload</span>}
            </button>
            <button className="nav-item" onClick={onManageDocuments}>
              <span className="nav-icon">📁</span>
              {!isCollapsed && <span className="nav-text">Manage</span>}
            </button>
          </div>
          {!isCollapsed && (
            <div className="files-list compact">
              {documents.slice(0, 6).map((doc) => (
                <div key={doc.id} className="file-item">
                  <span className="file-icon">📄</span>
                  <div className="file-info">
                    <span className="file-name" title={doc.filename}>
                      {doc.filename.length > 26 ? `${doc.filename.substring(0, 26)}...` : doc.filename}
                    </span>
                  </div>
                  {onDeleteDocument && (
                    <button
                      className="item-action-btn"
                      title="Delete document"
                      onClick={(e) => {
                        e.stopPropagation()
                        onDeleteDocument(doc.id)
                      }}
                    >
                      ✕
                    </button>
                  )}
                </div>
              ))}
              {documents.length === 0 && (
                <div className="empty-row">No documents yet</div>
              )}
            </div>
          )}
        </div>

        {/* Conversations */}
        <div className="sidebar-section">
          <div className="section-header">
            {!isCollapsed && <h4>Conversations</h4>}
            {!isCollapsed && <span className="file-count">{conversations.length}</span>}
          </div>
          <div className="conversations-list compact">
            {conversations.length === 0 && !isCollapsed && (
              <div className="empty-row">No conversations yet</div>
            )}
            {conversations.map((conv) => (
              <button
                key={conv.id}
                className={`conversation-chip ${currentConversationId === conv.id ? 'active' : ''}`}
                onClick={() => onConversationSelect(conv.id)}
                title={conv.title || 'Untitled conversation'}
              >
                <span className="chip-title">
                  {(conv.title || 'Untitled').length > 24
                    ? `${(conv.title || 'Untitled').substring(0, 24)}...`
                    : conv.title || 'Untitled'}
                </span>
                <span className="chip-meta">{conv.message_count || 0} msgs</span>
                {onDeleteConversation && (
                  <span
                    className="chip-delete"
                    title="Delete conversation"
                    onClick={(e) => {
                      e.stopPropagation()
                      onDeleteConversation(conv.id)
                    }}
                  >
                    ✕
                  </span>
                )}
              </button>
            ))}
          </div>
        </div>
      </div>

      <div className="sidebar-footer">
        {!isCollapsed && (
          <div className="footer-content">
            <p className="footer-text">
              Chat with your documents in one place. Upload, manage, and continue conversations seamlessly.
            </p>
          </div>
        )}
      </div>
    </div>
  )
}

export default Sidebar
