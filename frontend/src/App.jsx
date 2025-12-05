import { useState, useEffect, useCallback } from 'react'
import axios from 'axios'
import Sidebar from './components/Sidebar'
import UploadPage from './components/UploadPage'
import ChatPage from './components/ChatPage'
import DocumentManager from './components/DocumentManager'
import './App.css'

function App() {
  const [uploadedFiles, setUploadedFiles] = useState([])
  const [documents, setDocuments] = useState([])
  const [conversations, setConversations] = useState([])
  const [currentConversationId, setCurrentConversationId] = useState(null)
  const [showUploadModal, setShowUploadModal] = useState(false)
  const [showDocumentsModal, setShowDocumentsModal] = useState(false)

  const fetchDocuments = useCallback(async () => {
    try {
      const response = await axios.get('/api/documents')
      if (response.data.success) {
        setDocuments(response.data.documents || [])
      }
    } catch (error) {
      console.error('Error fetching documents:', error)
    }
  }, [])

  const fetchConversations = useCallback(async () => {
    try {
      const response = await axios.get('/api/conversations')
      if (response.data.success) {
        setConversations(response.data.conversations || [])
      }
    } catch (error) {
      console.error('Error fetching conversations:', error)
    }
  }, [])

  useEffect(() => {
    fetchDocuments()
    fetchConversations()
  }, [fetchDocuments, fetchConversations])

  const handleNewConversation = () => {
    setCurrentConversationId(null)
  }

  const handleConversationSelect = (conversationId) => {
    setCurrentConversationId(conversationId)
  }

  const handleConversationChange = (conversationId) => {
    setCurrentConversationId(conversationId)
    fetchConversations()
  }

  const handleUploadSuccess = (filenames) => {
    const fileArray = Array.isArray(filenames) ? filenames : [filenames]
    setUploadedFiles(prev => [...prev, ...fileArray])
    setShowUploadModal(false)
    fetchDocuments()
  }

  const handleDeleteDocument = async (documentId) => {
    if (!documentId) return
    const confirmed = window.confirm('Delete this document?')
    if (!confirmed) return
    try {
      await axios.delete(`/api/documents/${documentId}`)
      fetchDocuments()
    } catch (error) {
      console.error('Error deleting document:', error)
    }
  }

  const handleDeleteConversation = async (conversationId) => {
    if (!conversationId) return
    const confirmed = window.confirm('Delete this conversation?')
    if (!confirmed) return
    try {
      await axios.delete(`/api/conversations/${conversationId}`)
      if (currentConversationId === conversationId) {
        setCurrentConversationId(null)
      }
      fetchConversations()
    } catch (error) {
      console.error('Error deleting conversation:', error)
    }
  }

  return (
    <div className="app">
      <Sidebar
        documents={documents}
        conversations={conversations}
        onStartNewConversation={handleNewConversation}
        onConversationSelect={handleConversationSelect}
        currentConversationId={currentConversationId}
        onUploadClick={() => setShowUploadModal(true)}
        onManageDocuments={() => setShowDocumentsModal(true)}
        onDeleteDocument={handleDeleteDocument}
        onDeleteConversation={handleDeleteConversation}
      />

      <main className="main-content">
        <ChatPage
          uploadedFiles={uploadedFiles}
          conversationId={currentConversationId}
          onConversationChange={handleConversationChange}
        />
      </main>

      {/* Upload Modal */}
      {showUploadModal && (
        <div className="modal-backdrop" onClick={() => setShowUploadModal(false)}>
          <div className="modal-container" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3>Upload Documents</h3>
              <button className="modal-close" onClick={() => setShowUploadModal(false)}>✕</button>
            </div>
            <UploadPage onUploadSuccess={handleUploadSuccess} />
          </div>
        </div>
      )}

      {/* Documents Modal */}
      {showDocumentsModal && (
        <div className="modal-backdrop" onClick={() => setShowDocumentsModal(false)}>
          <div className="modal-container wide" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3>Documents</h3>
              <button className="modal-close" onClick={() => setShowDocumentsModal(false)}>✕</button>
            </div>
            <DocumentManager />
          </div>
        </div>
      )}
    </div>
  )
}

export default App

