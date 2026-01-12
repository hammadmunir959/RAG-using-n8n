import { useState, useRef, useCallback } from 'react';
import './UploadView.css';

const Icons = {
    upload: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4" /><path d="M17 8l-5-5-5 5M12 3v12" /></svg>,
    file: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z" /><path d="M14 2v6h6" /></svg>,
    x: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M18 6L6 18M6 6l12 12" /></svg>,
    check: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M20 6L9 17l-5-5" /></svg>,
    alert: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="10" /><path d="M12 8v4M12 16h.01" /></svg>,
};

const ALLOWED = ['.pdf', '.csv', '.json', '.txt'];

export default function UploadView({ onComplete, onCancel }) {
    const [files, setFiles] = useState([]);
    const [dragging, setDragging] = useState(false);
    const [uploading, setUploading] = useState(false);
    const [progress, setProgress] = useState(0);
    const [result, setResult] = useState(null);
    const inputRef = useRef(null);

    const isValid = (file) => {
        const ext = '.' + file.name.split('.').pop().toLowerCase();
        return ALLOWED.includes(ext);
    };

    const addFiles = (newFiles) => {
        const valid = Array.from(newFiles).filter(isValid);
        setFiles(prev => [...prev, ...valid]);
        setResult(null);
    };

    const handleDrag = useCallback((e, isDragging) => {
        e.preventDefault();
        e.stopPropagation();
        setDragging(isDragging);
    }, []);

    const handleDrop = useCallback((e) => {
        e.preventDefault();
        e.stopPropagation();
        setDragging(false);
        if (e.dataTransfer.files?.length) {
            addFiles(e.dataTransfer.files);
        }
    }, []);

    const handleInput = (e) => {
        if (e.target.files?.length) {
            addFiles(e.target.files);
        }
        e.target.value = '';
    };

    const removeFile = (idx) => {
        setFiles(prev => prev.filter((_, i) => i !== idx));
    };

    const clearFiles = () => {
        setFiles([]);
        setResult(null);
    };

    const uploadFiles = async () => {
        if (!files.length || uploading) return;

        setUploading(true);
        setProgress(0);
        setResult(null);

        const formData = new FormData();
        files.forEach(f => formData.append('files', f));

        try {
            const res = await fetch('/api/upload', {
                method: 'POST',
                body: formData
            });

            const data = await res.json();
            setProgress(100);

            if (data.success) {
                setResult({
                    type: 'success',
                    title: 'Upload Complete',
                    message: data.message || `${files.length} file(s) uploaded successfully`
                });
                setFiles([]);
                setTimeout(() => onComplete?.(), 1500);
            } else {
                setResult({
                    type: 'error',
                    title: 'Upload Failed',
                    message: data.detail || 'An error occurred'
                });
            }
        } catch (e) {
            setResult({
                type: 'error',
                title: 'Connection Error',
                message: 'Failed to connect. Is the backend running?'
            });
        }

        setUploading(false);
    };

    const formatSize = (bytes) => {
        if (bytes < 1024) return bytes + ' B';
        if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
        return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
    };

    return (
        <div className="upload-view">
            {/* Header */}
            <header className="upload-header">
                <h1 className="upload-header-title">Upload Documents</h1>
                <button className="close-btn" onClick={onCancel} title="Close">
                    {Icons.x}
                </button>
            </header>

            {/* Content */}
            <div className="upload-content">
                {/* Dropzone */}
                <div
                    className={`dropzone ${dragging ? 'dragging' : ''} ${uploading ? 'disabled' : ''}`}
                    onDragEnter={(e) => handleDrag(e, true)}
                    onDragOver={(e) => handleDrag(e, true)}
                    onDragLeave={(e) => handleDrag(e, false)}
                    onDrop={handleDrop}
                    onClick={() => !uploading && inputRef.current?.click()}
                >
                    <div className="dropzone-icon">{Icons.upload}</div>
                    <h2 className="dropzone-title">
                        {dragging ? 'Drop files here' : 'Drag and drop files'}
                    </h2>
                    <p className="dropzone-subtitle">or click to browse</p>
                    <button type="button" className="dropzone-btn">Select Files</button>
                    <div className="dropzone-formats">
                        {ALLOWED.map(ext => (
                            <span key={ext} className="format-tag">{ext.toUpperCase().slice(1)}</span>
                        ))}
                    </div>
                </div>

                <input
                    ref={inputRef}
                    type="file"
                    className="file-input"
                    multiple
                    accept={ALLOWED.join(',')}
                    onChange={handleInput}
                />

                {/* Selected Files */}
                {files.length > 0 && (
                    <div className="selected-files">
                        <div className="files-header">
                            <span className="files-title">Selected Files</span>
                            <span className="files-count">{files.length} file(s)</span>
                        </div>
                        <div className="files-list">
                            {files.map((file, idx) => (
                                <div key={`${file.name}-${idx}`} className="file-item">
                                    <div className="file-icon">{Icons.file}</div>
                                    <div className="file-info">
                                        <div className="file-name">{file.name}</div>
                                        <div className="file-size">{formatSize(file.size)}</div>
                                    </div>
                                    <button
                                        className="file-remove"
                                        onClick={() => removeFile(idx)}
                                        disabled={uploading}
                                    >
                                        {Icons.x}
                                    </button>
                                </div>
                            ))}
                        </div>
                    </div>
                )}

                {/* Actions */}
                {files.length > 0 && !result && (
                    <div className="upload-actions">
                        <button className="action-btn secondary" onClick={clearFiles} disabled={uploading}>
                            Clear All
                        </button>
                        <button
                            className="action-btn primary"
                            onClick={uploadFiles}
                            disabled={uploading}
                        >
                            {Icons.upload}
                            <span>{uploading ? 'Uploading...' : `Upload ${files.length} File${files.length > 1 ? 's' : ''}`}</span>
                        </button>
                    </div>
                )}

                {/* Progress */}
                {uploading && (
                    <div className="upload-progress">
                        <div className="progress-bar-bg">
                            <div className="progress-bar-fill" style={{ width: `${progress}%` }} />
                        </div>
                        <p className="progress-text">Uploading files...</p>
                    </div>
                )}

                {/* Result */}
                {result && (
                    <div className={`upload-result ${result.type}`}>
                        <div className="result-header">
                            <span className="result-icon">
                                {result.type === 'success' ? Icons.check : Icons.alert}
                            </span>
                            <span className="result-title">{result.title}</span>
                        </div>
                        <p className="result-message">{result.message}</p>
                    </div>
                )}
            </div>
        </div>
    );
}
