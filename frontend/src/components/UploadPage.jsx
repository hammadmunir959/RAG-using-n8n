import { useState } from 'react'
import axios from 'axios'
import './UploadPage.css'

function UploadPage({ onUploadSuccess }) {
  const [files, setFiles] = useState([])
  const [isDragging, setIsDragging] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [uploadProgress, setUploadProgress] = useState({})
  const [message, setMessage] = useState({ type: '', text: '' })

  const allowedTypes = ['application/pdf', 'text/csv', 'application/json', 'text/plain']
  const allowedExtensions = ['.pdf', '.csv', '.json', '.txt']

  const validateFile = (file) => {
    const fileExt = '.' + file.name.split('.').pop().toLowerCase()
    return allowedTypes.includes(file.type) || allowedExtensions.includes(fileExt)
  }

  const handleFilesSelect = (fileList) => {
    const fileArray = Array.from(fileList)
    const validFiles = fileArray.filter(validateFile)
    const invalidFiles = fileArray.filter(f => !validateFile(f))

    if (invalidFiles.length > 0) {
      setMessage({
        type: 'error',
        text: `${invalidFiles.length} file(s) were rejected. Only PDF, CSV, JSON, and TXT files are allowed.`
      })
    }

    if (validFiles.length > 0) {
      const newFiles = validFiles.map(file => ({
        file,
        id: Date.now() + Math.random(),
        status: 'pending',
        progress: 0
      }))
      setFiles(prev => [...prev, ...newFiles])
      setMessage({ type: '', text: '' })
    }
  }

  const handleDragOver = (e) => {
    e.preventDefault()
    setIsDragging(true)
  }

  const handleDragLeave = (e) => {
    e.preventDefault()
    setIsDragging(false)
  }

  const handleDrop = (e) => {
    e.preventDefault()
    setIsDragging(false)
    const droppedFiles = e.dataTransfer.files
    if (droppedFiles.length > 0) {
      handleFilesSelect(droppedFiles)
    }
  }

  const handleFileInput = (e) => {
    const selectedFiles = e.target.files
    if (selectedFiles.length > 0) {
      handleFilesSelect(selectedFiles)
    }
  }

  const removeFile = (fileId) => {
    setFiles(files.filter(f => f.id !== fileId))
  }

  const formatFileSize = (bytes) => {
    if (bytes < 1024) return bytes + ' B'
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(2) + ' KB'
    return (bytes / (1024 * 1024)).toFixed(2) + ' MB'
  }

  const handleUpload = async () => {
    if (files.length === 0) {
      setMessage({ type: 'error', text: 'Please select at least one file first' })
      return
    }

    setUploading(true)
    setMessage({ type: '', text: '' })

    // Update all files to uploading status
    setFiles(prev => prev.map(f => ({ ...f, status: 'uploading', progress: 0 })))

    try {
      const formData = new FormData()
      files.forEach(fileItem => {
        formData.append('files', fileItem.file)
      })

      const response = await axios.post('/api/upload', formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
        onUploadProgress: (progressEvent) => {
          const percentCompleted = Math.round((progressEvent.loaded * 100) / progressEvent.total)
          setUploadProgress({ overall: percentCompleted })
        }
      })

      if (response.data.success) {
        const results = response.data.results || []
        const errors = response.data.errors || []

        // Update file statuses
        setFiles(prev => prev.map((fileItem, index) => {
          const result = results.find(r => r.filename === fileItem.file.name)
          if (result) {
            return { ...fileItem, status: 'success', progress: 100 }
          }
          const error = errors.find(e => e.filename === fileItem.file.name)
          if (error) {
            return { ...fileItem, status: 'error', progress: 0 }
          }
          return fileItem
        }))

        const successCount = results.length
        const errorCount = errors.length

        if (errorCount === 0) {
          setMessage({
            type: 'success',
            text: `Successfully uploaded ${successCount} file(s)!`
          })
          // Clear files after a delay
          setTimeout(() => {
            setFiles([])
            document.getElementById('file-input').value = ''
            if (onUploadSuccess) {
              results.forEach(r => onUploadSuccess(r.filename))
            }
          }, 2000)
        } else {
          setMessage({
            type: 'warning',
            text: `Uploaded ${successCount} file(s) successfully, ${errorCount} failed.`
          })
        }
      }
    } catch (error) {
      let errorMessage = 'Failed to upload documents. Please try again.'
      
      if (error.code === 'ECONNREFUSED' || error.message?.includes('Network Error')) {
        errorMessage = 'Cannot connect to backend server. Make sure the backend is running on port 8001.'
      } else if (error.response?.status === 503) {
        errorMessage = 'Cannot connect to n8n. Make sure n8n is running.'
      } else if (error.response?.data?.detail) {
        errorMessage = error.response.data.detail
      } else if (error.response?.status === 500) {
        errorMessage = 'Server error. Check backend logs for details.'
      }
      
      setFiles(prev => prev.map(f => ({ ...f, status: 'error' })))
      setMessage({
        type: 'error',
        text: errorMessage,
      })
    } finally {
      setUploading(false)
      setUploadProgress({})
    }
  }

  return (
    <div className="upload-page">
      <div className="upload-container">
        <div className="upload-header">
          <h1>Upload Documents</h1>
          <p>Add PDF, CSV, JSON, or TXT files to your knowledge base (multiple files supported)</p>
        </div>

        <div className="upload-zone">
          <div
            className={`dropzone ${isDragging ? 'dragging' : ''} ${files.length > 0 ? 'has-files' : ''}`}
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
          >
            <div className="dropzone-content">
              <div className="upload-icon">{files.length > 0 ? '📄' : '📤'}</div>
              {files.length === 0 ? (
                <>
                  <h3 className="dropzone-title">Drag & drop your files here</h3>
                  <p className="dropzone-subtitle">or click to browse (multiple files supported)</p>
                  <label htmlFor="file-input" className="browse-btn">
                    Choose Files
                  </label>
                  <input
                    id="file-input"
                    type="file"
                    accept=".pdf,.csv,.json,.txt"
                    multiple
                    onChange={handleFileInput}
                    style={{ display: 'none' }}
                  />
                </>
              ) : (
                <div className="files-preview">
                  <h3 className="files-count">{files.length} file(s) selected</h3>
                </div>
              )}
            </div>
          </div>

          {files.length > 0 && (
            <div className="files-list">
              {files.map((fileItem) => (
                <div key={fileItem.id} className={`file-item ${fileItem.status}`}>
                  <div className="file-item-info">
                    <span className="file-icon">
                      {fileItem.status === 'success' ? '✓' :
                       fileItem.status === 'error' ? '✕' :
                       fileItem.status === 'uploading' ? '⏳' : '📄'}
                    </span>
                    <div className="file-details">
                      <span className="file-name">{fileItem.file.name}</span>
                      <span className="file-size">{formatFileSize(fileItem.file.size)}</span>
                    </div>
                  </div>
                  {fileItem.status === 'uploading' && (
                    <div className="progress-bar">
                      <div
                        className="progress-fill"
                        style={{ width: `${uploadProgress.overall || 0}%` }}
                      ></div>
                    </div>
                  )}
                  {fileItem.status !== 'uploading' && (
                    <button
                      className="remove-file-btn"
                      onClick={() => removeFile(fileItem.id)}
                      title="Remove file"
                    >
                      ✕
                    </button>
                  )}
                </div>
              ))}
            </div>
          )}

          {files.length > 0 && (
            <div className="upload-actions">
              <button
                className="clear-btn"
                onClick={() => {
                  setFiles([])
                  document.getElementById('file-input').value = ''
                }}
                disabled={uploading}
              >
                Clear All
              </button>
              <button
                className="upload-btn"
                onClick={handleUpload}
                disabled={uploading || files.length === 0}
              >
                {uploading ? (
                  <>
                    <span className="spinner"></span>
                    Uploading {files.length} file(s)...
                  </>
                ) : (
                  `Upload ${files.length} File(s)`
                )}
              </button>
            </div>
          )}
        </div>

        {message.text && (
          <div className={`message ${message.type}`}>
            <span className="message-icon">
              {message.type === 'success' ? '✓' :
               message.type === 'error' ? '⚠' :
               message.type === 'warning' ? '⚠' : 'ℹ'}
            </span>
            {message.text}
          </div>
        )}
      </div>
    </div>
  )
}

export default UploadPage

