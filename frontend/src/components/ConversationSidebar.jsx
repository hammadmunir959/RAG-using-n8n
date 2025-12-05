import { useState, useEffect, useRef } from 'react'
import axios from 'axios'
import './ConversationSidebar.css'

function ConversationSidebar({ currentConversationId, onConversationSelect, onNewConversation }) {
  const [conversations, setConversations] = useState([])
  const [loading, setLoading] = useState(true)
  const [editingId, setEditingId] = useState(null)
  const [editTitle, setEditTitle] = useState('')
  const abortControllerRef = useRef(null)

  useEffect(() => {
    loadConversations()

    // Cleanup function
    return () => {
      if (abortControllerRef.current) {
        abortControllerRef.current.abort()
      }
      setLoading(false)
      setEditingId(null)
      setEditTitle('')
    }
  }, [])

  const loadConversations = async () => {
    // Cancel previous request if any
    if (abortControllerRef.current) {
      abortControllerRef.current.abort()
    }
    abortControllerRef.current = new AbortController()

    try {
      setLoading(true)
      const response = await axios.get('/api/conversations', {
        signal: abortControllerRef.current.signal
      })
      if (response.data.success) {
        setConversations(response.data.conversations || [])
      }
    } catch (error) {
      // Ignore abort errors
      if (error.name !== 'CanceledError' && error.name !== 'AbortError') {
        console.error('Error loading conversations:', error)
      }
    } finally {
      setLoading(false)
    }
  }

  const handleDelete = async (conversationId, e) => {
    e.stopPropagation()
    if (!window.confirm('Are you sure you want to delete this conversation?')) {
      return
    }

    try {
      const response = await axios.delete(`/api/conversations/${conversationId}`)
      if (response.data.success) {
        setConversations(conversations.filter(conv => conv.id !== conversationId))
        if (currentConversationId === conversationId) {
          onNewConversation()
        }
      }
    } catch (error) {
      console.error('Error deleting conversation:', error)
      alert('Failed to delete conversation. Please try again.')
    }
  }

  const handleEditStart = (conversation, e) => {
    e.stopPropagation()
    setEditingId(conversation.id)
    setEditTitle(conversation.title || '')
  }

  const handleEditSave = async (conversationId, e) => {
    e.stopPropagation()
    try {
      const response = await axios.patch(`/api/conversations/${conversationId}/title`, {
        title: editTitle
      })
      if (response.data.success) {
        setConversations(conversations.map(conv =>
          conv.id === conversationId
            ? { ...conv, title: editTitle }
            : conv
        ))
        setEditingId(null)
        setEditTitle('')
      }
    } catch (error) {
      console.error('Error updating conversation title:', error)
      alert('Failed to update conversation title.')
    }
  }

  const handleEditCancel = () => {
    setEditingId(null)
    setEditTitle('')
  }

  const formatDate = (dateString) => {
    const date = new Date(dateString)
    const now = new Date()
    const diffMs = now - date
    const diffMins = Math.floor(diffMs / 60000)
    const diffHours = Math.floor(diffMs / 3600000)
    const diffDays = Math.floor(diffMs / 86400000)

    if (diffMins < 1) return 'Just now'
    if (diffMins < 60) return `${diffMins}m ago`
    if (diffHours < 24) return `${diffHours}h ago`
    if (diffDays < 7) return `${diffDays}d ago`
    return date.toLocaleDateString()
  }

  return (
    <div className="conversation-sidebar">
      <div className="sidebar-header">
        <h3>Conversations</h3>
        <button className="new-conv-btn" onClick={onNewConversation} title="New conversation">
          ➕
        </button>
      </div>

      {loading ? (
        <div className="loading-conversations">
          <div className="spinner-small"></div>
          <span>Loading...</span>
        </div>
      ) : conversations.length === 0 ? (
        <div className="empty-conversations">
          <p>No conversations yet</p>
          <p className="empty-hint">Start chatting to create one!</p>
        </div>
      ) : (
        <div className="conversations-list">
          {conversations.map((conv) => (
            <div
              key={conv.id}
              className={`conversation-item ${currentConversationId === conv.id ? 'active' : ''}`}
              onClick={() => onConversationSelect(conv.id)}
            >
              {editingId === conv.id ? (
                <div className="conversation-edit" onClick={(e) => e.stopPropagation()}>
                  <input
                    type="text"
                    value={editTitle}
                    onChange={(e) => setEditTitle(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') {
                        handleEditSave(conv.id, e)
                      } else if (e.key === 'Escape') {
                        handleEditCancel()
                      }
                    }}
                    className="edit-input"
                    autoFocus
                  />
                  <div className="edit-actions">
                    <button
                      className="save-btn"
                      onClick={(e) => handleEditSave(conv.id, e)}
                    >
                      ✓
                    </button>
                    <button
                      className="cancel-btn"
                      onClick={handleEditCancel}
                    >
                      ✕
                    </button>
                  </div>
                </div>
              ) : (
                <>
                  <div className="conversation-content">
                    <div className="conversation-title">
                      {conv.title || 'New Conversation'}
                    </div>
                    <div className="conversation-meta">
                      <span className="message-count">{conv.message_count || 0} messages</span>
                      <span className="conversation-date">{formatDate(conv.updated_at)}</span>
                    </div>
                  </div>
                  <div className="conversation-actions">
                    <button
                      className="edit-btn"
                      onClick={(e) => handleEditStart(conv, e)}
                      title="Edit title"
                    >
                      ✏️
                    </button>
                    <button
                      className="delete-btn"
                      onClick={(e) => handleDelete(conv.id, e)}
                      title="Delete conversation"
                    >
                      🗑️
                    </button>
                  </div>
                </>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

export default ConversationSidebar

