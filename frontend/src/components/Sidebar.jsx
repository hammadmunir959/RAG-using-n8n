import './Sidebar.css';

// Minimal SVG Icons
const Icons = {
  plus: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M12 5v14M5 12h14" /></svg>,
  chat: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z" /></svg>,
  file: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z" /><path d="M14 2v6h6M16 13H8M16 17H8M10 9H8" /></svg>,
  upload: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4" /><path d="M17 8l-5-5-5 5M12 3v12" /></svg>,
  settings: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="3" /><path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42" /></svg>,
  message: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M21 11.5a8.38 8.38 0 01-.9 3.8 8.5 8.5 0 01-7.6 4.7 8.38 8.38 0 01-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 01-.9-3.8 8.5 8.5 0 014.7-7.6 8.38 8.38 0 013.8-.9h.5a8.48 8.48 0 018 8v.5z" /></svg>,
  trash: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M3 6h18M19 6v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6m3 0V4a2 2 0 012-2h4a2 2 0 012 2v2" /></svg>,
};

export default function Sidebar({
  activeView,
  onViewChange,
  conversations,
  activeConversationId,
  onSelectConversation,
  onNewConversation,
  onDeleteConversation,
  stats
}) {
  return (
    <aside className="sidebar">
      {/* Brand */}
      <div className="sidebar-brand">
        <div className="brand-logo">DI</div>
        <span className="brand-text">DocIntel</span>
      </div>

      {/* New Chat */}
      <div className="sidebar-action">
        <button className="new-chat-btn" onClick={onNewConversation}>
          {Icons.plus}
          <span>New Chat</span>
        </button>
      </div>

      {/* Navigation */}
      <nav className="sidebar-nav">
        <div className="nav-group">
          <div className="nav-label">Menu</div>

          <button
            className={`nav-item ${activeView === 'chat' ? 'active' : ''}`}
            onClick={() => onViewChange('chat')}
          >
            {Icons.chat}
            <span className="nav-item-text">Chat</span>
          </button>

          <button
            className={`nav-item ${activeView === 'documents' ? 'active' : ''}`}
            onClick={() => onViewChange('documents')}
          >
            {Icons.file}
            <span className="nav-item-text">Documents</span>
            {stats.documents > 0 && (
              <span className="nav-badge">{stats.documents}</span>
            )}
          </button>

          <button
            className={`nav-item ${activeView === 'upload' ? 'active' : ''}`}
            onClick={() => onViewChange('upload')}
          >
            {Icons.upload}
            <span className="nav-item-text">Upload</span>
          </button>

          <button
            className={`nav-item ${activeView === 'settings' ? 'active' : ''}`}
            onClick={() => onViewChange('settings')}
          >
            {Icons.settings}
            <span className="nav-item-text">Settings</span>
          </button>
        </div>
      </nav>

      {/* Conversations */}
      <div className="sidebar-conversations">
        <div className="conversations-header">
          <span className="conversations-title">History</span>
          <span className="conversations-count">{conversations.length}</span>
        </div>

        <div className="conversations-list">
          {conversations.length === 0 ? (
            <div className="conversations-empty">No conversations yet</div>
          ) : (
            conversations.map(conv => (
              <button
                key={conv.id}
                className={`conversation-item ${activeConversationId === conv.id ? 'active' : ''}`}
                onClick={() => onSelectConversation(conv.id)}
              >
                <span className="conversation-icon">{Icons.message}</span>
                <span className="conversation-title">{conv.title || 'Untitled'}</span>
                <button
                  className="conversation-delete"
                  onClick={(e) => {
                    e.stopPropagation();
                    onDeleteConversation(conv.id);
                  }}
                  title="Delete"
                >
                  {Icons.trash}
                </button>
              </button>
            ))
          )}
        </div>
      </div>

      {/* Footer Stats */}
      <div className="sidebar-footer">
        <div className="sidebar-stats">
          <div className="stat-item">
            <div className="stat-value">{stats.documents}</div>
            <div className="stat-label">Docs</div>
          </div>
          <div className="stat-item">
            <div className="stat-value">{stats.conversations}</div>
            <div className="stat-label">Chats</div>
          </div>
          <div className="stat-item">
            <div className="stat-value">{stats.messages}</div>
            <div className="stat-label">Msgs</div>
          </div>
        </div>
      </div>
    </aside>
  );
}
