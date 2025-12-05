import { useState, useEffect, useRef } from 'react'
import axios from 'axios'
import './DocumentManager.css'

function DocumentManager() {
  const [documents, setDocuments] = useState([])
  const [loading, setLoading] = useState(true)
  const [filter, setFilter] = useState('all') // all, pdf, csv, json, txt
  const [searchTerm, setSearchTerm] = useState('')
  const [selectedDocs, setSelectedDocs] = useState([])
  const [deleting, setDeleting] = useState(false)
  const abortControllerRef = useRef(null)

  useEffect(() => {
    loadDocuments()

    // Cleanup function
    return () => {
      if (abortControllerRef.current) {
        abortControllerRef.current.abort()
      }
      setLoading(false)
      setDeleting(false)
    }
  }, [])

  const loadDocuments = async () => {
    // Cancel previous request if any
    if (abortControllerRef.current) {
      abortControllerRef.current.abort()
    }
    abortControllerRef.current = new AbortController()

    try {
      setLoading(true)
      const response = await axios.get('/api/documents', {
        signal: abortControllerRef.current.signal
      })
      if (response.data.success) {
        setDocuments(response.data.documents || [])
      }
    } catch (error) {
      // Ignore abort errors
      if (error.name !== 'CanceledError' && error.name !== 'AbortError') {
        console.error('Error loading documents:', error)
      }
    } finally {
      setLoading(false)
    }
  }

  const handleDelete = async (docId) => {
    if (!window.confirm('Are you sure you want to delete this document?')) {
      return
    }

    try {
      setDeleting(true)
      const response = await axios.delete(`/api/documents/${docId}`)
      if (response.data.success) {
        setDocuments(documents.filter(doc => doc.id !== docId))
        setSelectedDocs(selectedDocs.filter(id => id !== docId))
      }
    } catch (error) {
      console.error('Error deleting document:', error)
      alert('Failed to delete document. Please try again.')
    } finally {
      setDeleting(false)
    }
  }

  const handleBulkDelete = async () => {
    if (selectedDocs.length === 0) return
    if (!window.confirm(`Are you sure you want to delete ${selectedDocs.length} document(s)?`)) {
      return
    }

    try {
      setDeleting(true)
      const deletePromises = selectedDocs.map(id => axios.delete(`/api/documents/${id}`))
      await Promise.all(deletePromises)
      setDocuments(documents.filter(doc => !selectedDocs.includes(doc.id)))
      setSelectedDocs([])
    } catch (error) {
      console.error('Error deleting documents:', error)
      alert('Failed to delete some documents. Please try again.')
    } finally {
      setDeleting(false)
    }
  }

  const toggleSelect = (docId) => {
    setSelectedDocs(prev =>
      prev.includes(docId)
        ? prev.filter(id => id !== docId)
        : [...prev, docId]
    )
  }

  const toggleSelectAll = () => {
    if (selectedDocs.length === filteredDocuments.length) {
      setSelectedDocs([])
    } else {
      setSelectedDocs(filteredDocuments.map(doc => doc.id))
    }
  }

  const formatFileSize = (bytes) => {
    if (bytes < 1024) return bytes + ' B'
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(2) + ' KB'
    return (bytes / (1024 * 1024)).toFixed(2) + ' MB'
  }

  const formatDate = (dateString) => {
    const date = new Date(dateString)
    return date.toLocaleDateString() + ' ' + date.toLocaleTimeString()
  }

  const getFileIcon = (fileType) => {
    const icons = {
      pdf: '📄',
      csv: '📊',
      json: '📋',
      txt: '📝'
    }
    return icons[fileType] || '📄'
  }

  const filteredDocuments = documents.filter(doc => {
    const matchesFilter = filter === 'all' || doc.file_type === filter
    const matchesSearch = doc.filename.toLowerCase().includes(searchTerm.toLowerCase())
    return matchesFilter && matchesSearch
  })

  if (loading) {
    return (
      <div className="document-manager">
        <div className="loading-container">
          <div className="spinner"></div>
          <p>Loading documents...</p>
        </div>
      </div>
    )
  }

  return (
    <div className="document-manager">
      <div className="doc-manager-header">
        <h1>Document Management</h1>
        <button className="refresh-btn" onClick={loadDocuments} disabled={loading}>
          🔄 Refresh
        </button>
      </div>

      <div className="doc-manager-controls">
        <div className="search-box">
          <input
            type="text"
            placeholder="Search documents..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="search-input"
          />
        </div>

        <div className="filter-buttons">
          <button
            className={`filter-btn ${filter === 'all' ? 'active' : ''}`}
            onClick={() => setFilter('all')}
          >
            All ({documents.length})
          </button>
          <button
            className={`filter-btn ${filter === 'pdf' ? 'active' : ''}`}
            onClick={() => setFilter('pdf')}
          >
            PDF ({documents.filter(d => d.file_type === 'pdf').length})
          </button>
          <button
            className={`filter-btn ${filter === 'csv' ? 'active' : ''}`}
            onClick={() => setFilter('csv')}
          >
            CSV ({documents.filter(d => d.file_type === 'csv').length})
          </button>
          <button
            className={`filter-btn ${filter === 'json' ? 'active' : ''}`}
            onClick={() => setFilter('json')}
          >
            JSON ({documents.filter(d => d.file_type === 'json').length})
          </button>
          <button
            className={`filter-btn ${filter === 'txt' ? 'active' : ''}`}
            onClick={() => setFilter('txt')}
          >
            TXT ({documents.filter(d => d.file_type === 'txt').length})
          </button>
        </div>

        {selectedDocs.length > 0 && (
          <div className="bulk-actions">
            <span>{selectedDocs.length} selected</span>
            <button
              className="bulk-delete-btn"
              onClick={handleBulkDelete}
              disabled={deleting}
            >
              {deleting ? 'Deleting...' : `Delete ${selectedDocs.length}`}
            </button>
          </div>
        )}
      </div>

      {filteredDocuments.length === 0 ? (
        <div className="empty-state">
          <div className="empty-icon">📁</div>
          <h3>No documents found</h3>
          <p>
            {searchTerm || filter !== 'all'
              ? 'Try adjusting your search or filter'
              : 'Upload your first document to get started'}
          </p>
        </div>
      ) : (
        <div className="documents-grid">
          {filteredDocuments.map((doc) => (
            <div key={doc.id} className="document-card">
              <div className="card-header">
                <input
                  type="checkbox"
                  checked={selectedDocs.includes(doc.id)}
                  onChange={() => toggleSelect(doc.id)}
                  className="doc-checkbox"
                />
                <span className="file-icon">{getFileIcon(doc.file_type)}</span>
                <span className="file-type-badge">{doc.file_type.toUpperCase()}</span>
              </div>
              <div className="card-body">
                <h3 className="doc-filename" title={doc.filename}>
                  {doc.filename.length > 30
                    ? doc.filename.substring(0, 30) + '...'
                    : doc.filename}
                </h3>
                <div className="doc-meta">
                  <div className="meta-item">
                    <span className="meta-label">Size:</span>
                    <span className="meta-value">{formatFileSize(doc.file_size)}</span>
                  </div>
                  <div className="meta-item">
                    <span className="meta-label">Uploaded:</span>
                    <span className="meta-value">{formatDate(doc.upload_date)}</span>
                  </div>
                  <div className="meta-item">
                    <span className="meta-label">Status:</span>
                    <span className={`status-badge status-${doc.status}`}>
                      {doc.status}
                    </span>
                  </div>
                </div>
              </div>
              <div className="card-actions">
                <button
                  className="delete-btn"
                  onClick={() => handleDelete(doc.id)}
                  disabled={deleting}
                  title="Delete document"
                >
                  🗑️ Delete
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

export default DocumentManager

