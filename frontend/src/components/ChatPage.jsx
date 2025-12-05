import { useState, useRef, useEffect } from 'react'
import axios from 'axios'
import CitationBadge from './CitationBadge'
import './ChatPage.css'

function ChatPage({ uploadedFiles, conversationId, onConversationChange }) {
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [streaming, setStreaming] = useState(false)
  const [currentConversationId, setCurrentConversationId] = useState(conversationId)
  const [loadingMessages, setLoadingMessages] = useState(false)
  const messagesEndRef = useRef(null)
  const streamingMessageRef = useRef(null)
  const abortControllerRef = useRef(null)

  useEffect(() => {
    setCurrentConversationId(conversationId || null)
  }, [conversationId])

  useEffect(() => {
    // Cleanup function
    return () => {
      // Cancel any pending requests when component unmounts
      if (abortControllerRef.current) {
        abortControllerRef.current.abort()
      }
      setLoading(false)
      setStreaming(false)
      setLoadingMessages(false)
    }
  }, [])

  useEffect(() => {
    // Cancel previous request if conversation changes
    if (abortControllerRef.current) {
      abortControllerRef.current.abort()
    }

    // Create new abort controller for this request
    abortControllerRef.current = new AbortController()

    if (currentConversationId) {
      loadConversation(currentConversationId)
    } else {
      // New conversation - show welcome message
      setMessages([
        {
          role: 'assistant',
          content: uploadedFiles.length > 0
            ? `Hello! I can see you have ${uploadedFiles.length} document${uploadedFiles.length > 1 ? 's' : ''} uploaded. Ask me questions about ${uploadedFiles.length > 1 ? 'them' : 'it'}!`
            : "Hello! I'm your document intelligence assistant. Upload documents first, then ask me questions about them!",
          sources: []
        },
      ])
    }

    // Cleanup on conversation change
    return () => {
      if (abortControllerRef.current) {
        abortControllerRef.current.abort()
      }
    }
  }, [currentConversationId, uploadedFiles.length])

  useEffect(() => {
    scrollToBottom()
  }, [messages])

  const loadConversation = async (convId) => {
    try {
      setLoadingMessages(true)
      const response = await axios.get(`/api/conversations/${convId}`, {
        signal: abortControllerRef.current?.signal
      })
      if (response.data.success) {
        const convMessages = response.data.conversation.messages.map(msg => ({
          role: msg.role,
          content: msg.content,
          sources: msg.sources || [],
          id: msg.id
        }))
        setMessages(convMessages)
        if (onConversationChange) {
          onConversationChange(convId)
        }
      }
    } catch (error) {
      // Ignore abort errors (component unmounted or conversation changed)
      if (error.name !== 'CanceledError' && error.name !== 'AbortError') {
        console.error('Error loading conversation:', error)
      }
    } finally {
      setLoadingMessages(false)
    }
  }

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  const handleSend = async (e) => {
    e.preventDefault()
    if (!input.trim() || loading || streaming) return

    const userMessage = input.trim()
    setInput('')
    setMessages((prev) => [...prev, { role: 'user', content: userMessage, sources: [] }])
    setLoading(true)

    try {
      // Cancel any previous request
      if (abortControllerRef.current) {
        abortControllerRef.current.abort()
      }
      abortControllerRef.current = new AbortController()

      const response = await axios.post('/api/chat', {
        message: userMessage,
        conversation_id: currentConversationId || null
      }, {
        signal: abortControllerRef.current.signal
      })

      if (response.data.success) {
        // Update conversation ID if this is a new conversation
        if (!currentConversationId && response.data.conversation_id) {
          setCurrentConversationId(response.data.conversation_id)
          if (onConversationChange) {
            onConversationChange(response.data.conversation_id)
          }
        }

        // Get source document metadata
        const sources = response.data.sources || []
        const sourceDocs = sources.map(s => ({
          id: s.id,
          filename: s.filename,
          file_type: s.file_type
        }))

        setMessages((prev) => [
          ...prev,
          {
            role: 'assistant',
            content: response.data.response,
            sources: sourceDocs
          },
        ])
      } else {
        throw new Error('Failed to get response')
      }
    } catch (error) {
      // Ignore abort errors (request was cancelled)
      if (error.name === 'CanceledError' || error.name === 'AbortError') {
        return
      }

      let errorMessage = 'Sorry, I encountered an error. Please try again.'
      
      if (error.code === 'ECONNREFUSED' || error.message?.includes('Network Error')) {
        errorMessage = 'Cannot connect to backend server. Make sure the backend is running on port 8001.'
      } else if (error.response?.status === 503) {
        errorMessage = 'Cannot connect to n8n. Make sure n8n is running.'
      } else if (error.response?.data?.detail) {
        errorMessage = `Error: ${error.response.data.detail}`
      } else if (error.message) {
        errorMessage = `Error: ${error.message}`
      }
      
      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          content: errorMessage,
          sources: []
        },
      ])
    } finally {
      setLoading(false)
    }
  }

  const handleSourceClick = (source) => {
    // Could navigate to document manager or show document details
    console.log('Source clicked:', source)
    // For now, just log it - can be enhanced later
  }

  return (
    <div className="chat-page">
      <div className="chat-header">
        <h1>Document Assistant</h1>
        {uploadedFiles.length > 0 && (
          <div className="files-indicator">
            <span className="files-icon">📄</span>
            <span className="files-text">
              {uploadedFiles.length} document{uploadedFiles.length > 1 ? 's' : ''} ready
            </span>
          </div>
        )}
      </div>

      {loadingMessages ? (
        <div className="loading-messages">
          <div className="spinner"></div>
          <p>Loading conversation...</p>
        </div>
      ) : (
        <div className="chat-messages">
          {messages.map((msg, idx) => (
            <div key={msg.id || idx} className={`message ${msg.role}`}>
              <div className="message-wrapper">
                <div className="message-avatar">
                  {msg.role === 'user' ? '👤' : '🤖'}
                </div>
                <div className="message-content">
                  <div className="message-text">{msg.content}</div>
                  {msg.role === 'assistant' && msg.sources && msg.sources.length > 0 && (
                    <CitationBadge
                      sources={msg.sources}
                      onSourceClick={handleSourceClick}
                    />
                  )}
                </div>
              </div>
            </div>
          ))}
          {loading && (
            <div className="message assistant">
              <div className="message-wrapper">
                <div className="message-avatar">🤖</div>
                <div className="message-content">
                  <div className="typing-indicator">
                    <span></span>
                    <span></span>
                    <span></span>
                  </div>
                </div>
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>
      )}

      <div className="chat-input-container">
        <form className="chat-input-form" onSubmit={handleSend}>
          <div className="input-wrapper">
            <input
              type="text"
              className="chat-input"
              placeholder={uploadedFiles.length > 0 ? "Ask a question about your documents..." : "Upload documents first to start chatting..."}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              disabled={loading || streaming}
            />
            <button
              type="submit"
              className="send-btn"
              disabled={loading || streaming || !input.trim()}
            >
              {loading ? '⏳' : '➤'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

export default ChatPage

