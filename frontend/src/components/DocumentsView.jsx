import { useState, useMemo } from 'react';
import './DocumentsView.css';

const Icons = {
    file: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z" /><path d="M14 2v6h6M16 13H8M16 17H8M10 9H8" /></svg>,
    search: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="11" cy="11" r="8" /><path d="M21 21l-4.35-4.35" /></svg>,
    grid: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="3" y="3" width="7" height="7" /><rect x="14" y="3" width="7" height="7" /><rect x="3" y="14" width="7" height="7" /><rect x="14" y="14" width="7" height="7" /></svg>,
    list: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><line x1="8" y1="6" x2="21" y2="6" /><line x1="8" y1="12" x2="21" y2="12" /><line x1="8" y1="18" x2="21" y2="18" /><line x1="3" y1="6" x2="3.01" y2="6" /><line x1="3" y1="12" x2="3.01" y2="12" /><line x1="3" y1="18" x2="3.01" y2="18" /></svg>,
    refresh: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M23 4v6h-6M1 20v-6h6" /><path d="M3.51 9a9 9 0 0114.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0020.49 15" /></svg>,
    upload: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4" /><path d="M17 8l-5-5-5 5M12 3v12" /></svg>,
    trash: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M3 6h18M19 6v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6m3 0V4a2 2 0 012-2h4a2 2 0 012 2v2" /></svg>,
    calendar: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="3" y="4" width="18" height="18" rx="2" /><line x1="16" y1="2" x2="16" y2="6" /><line x1="8" y1="2" x2="8" y2="6" /><line x1="3" y1="10" x2="21" y2="10" /></svg>,
    folder: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M22 19a2 2 0 01-2 2H4a2 2 0 01-2-2V5a2 2 0 012-2h5l2 3h9a2 2 0 012 2z" /></svg>,
    sparkle: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707" /></svg>,
    retry: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M1 4v6h6" /><path d="M3.51 15a9 9 0 102.13-9.36L1 10" /></svg>,
};

export default function DocumentsView({ documents, onDelete, onRefresh, isLoading, onUploadClick }) {
    const [search, setSearch] = useState('');
    const [viewMode, setViewMode] = useState('grid');
    const [deletingId, setDeletingId] = useState(null);
    const [generatingId, setGeneratingId] = useState(null);
    const [expandedDoc, setExpandedDoc] = useState(null);

    const filtered = useMemo(() => {
        if (!search.trim()) return documents;
        const q = search.toLowerCase();
        return documents.filter(d =>
            d.filename.toLowerCase().includes(q) ||
            d.file_type?.toLowerCase().includes(q) ||
            d.summary?.toLowerCase().includes(q)
        );
    }, [documents, search]);

    const handleDelete = async (id) => {
        if (deletingId) return;
        setDeletingId(id);
        await onDelete(id);
        setDeletingId(null);
    };

    const handleGenerateSummary = async (id) => {
        if (generatingId) return;
        setGeneratingId(id);
        try {
            await fetch(`/api/documents/${id}/generate-summary`, { method: 'POST' });
            // Refresh after a short delay to show new status
            setTimeout(() => {
                onRefresh();
                setGeneratingId(null);
            }, 1000);
        } catch (e) {
            console.error('Failed to generate summary:', e);
            setGeneratingId(null);
        }
    };

    const formatSize = (bytes) => {
        if (!bytes) return '-';
        if (bytes < 1024) return bytes + ' B';
        if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
        return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
    };

    const formatDate = (str) => {
        if (!str) return '-';
        return new Date(str).toLocaleDateString('en-US', {
            month: 'short',
            day: 'numeric'
        });
    };

    const getSummaryStatusLabel = (status) => {
        switch (status) {
            case 'completed': return 'AI Summary';
            case 'generating': return 'Generating...';
            case 'failed': return 'Retry';
            default: return 'Pending';
        }
    };

    const renderSkeleton = () => (
        <div className="docs-loading">
            {[1, 2, 3, 4, 5, 6].map(i => (
                <div key={i} className="skeleton-card">
                    <div className="skeleton-header">
                        <div className="skeleton-icon skeleton"></div>
                        <div className="skeleton-text">
                            <div className="skeleton-title skeleton"></div>
                            <div className="skeleton-subtitle skeleton"></div>
                        </div>
                    </div>
                    <div className="skeleton-footer skeleton"></div>
                </div>
            ))}
        </div>
    );

    const renderEmpty = () => (
        <div className="docs-empty">
            <div className="empty-icon">{Icons.folder}</div>
            <h2 className="empty-title">
                {search ? 'No results found' : 'No documents yet'}
            </h2>
            <p className="empty-text">
                {search
                    ? 'Try adjusting your search query'
                    : 'Upload documents to start analyzing them with AI'
                }
            </p>
            {!search && (
                <button className="empty-action" onClick={onUploadClick}>
                    {Icons.upload}
                    <span>Upload Documents</span>
                </button>
            )}
        </div>
    );

    const renderSummary = (doc) => {
        if (!doc.summary && doc.summary_status !== 'generating') {
            return null;
        }

        return (
            <div className="doc-summary">
                <div className="summary-header">
                    <span className={`summary-status ${doc.summary_status}`}>
                        {Icons.sparkle}
                        {getSummaryStatusLabel(doc.summary_status)}
                    </span>
                    {doc.summary_status === 'failed' && (
                        <button
                            className="summary-retry-btn"
                            onClick={(e) => {
                                e.stopPropagation();
                                handleGenerateSummary(doc.id);
                            }}
                            disabled={generatingId === doc.id}
                        >
                            {Icons.retry}
                        </button>
                    )}
                </div>
                {doc.summary ? (
                    <p className="summary-text">{doc.summary}</p>
                ) : doc.summary_status === 'generating' ? (
                    <p className="summary-text generating">Analyzing document content...</p>
                ) : null}
            </div>
        );
    };

    return (
        <div className="documents-view">
            {/* Header */}
            <header className="docs-header">
                <div className="docs-header-left">
                    <h1 className="docs-header-title">Documents</h1>
                    <span className="docs-count">{documents.length} files</span>
                </div>
                <div className="docs-header-right">
                    <button className="header-btn" onClick={onRefresh}>
                        {Icons.refresh}
                        <span>Refresh</span>
                    </button>
                    <button className="header-btn header-btn-primary" onClick={onUploadClick}>
                        {Icons.upload}
                        <span>Upload</span>
                    </button>
                </div>
            </header>

            {/* Toolbar */}
            <div className="docs-toolbar">
                <div className="search-box">
                    <span className="search-icon">{Icons.search}</span>
                    <input
                        type="text"
                        className="search-input"
                        placeholder="Search documents..."
                        value={search}
                        onChange={(e) => setSearch(e.target.value)}
                    />
                </div>
                <div className="view-toggle">
                    <button
                        className={`view-btn ${viewMode === 'grid' ? 'active' : ''}`}
                        onClick={() => setViewMode('grid')}
                        title="Grid view"
                    >
                        {Icons.grid}
                    </button>
                    <button
                        className={`view-btn ${viewMode === 'list' ? 'active' : ''}`}
                        onClick={() => setViewMode('list')}
                        title="List view"
                    >
                        {Icons.list}
                    </button>
                </div>
            </div>

            {/* Content */}
            <div className="docs-content">
                {isLoading ? renderSkeleton() :
                    filtered.length === 0 ? renderEmpty() :
                        viewMode === 'grid' ? (
                            <div className="docs-grid">
                                {filtered.map(doc => (
                                    <div
                                        key={doc.id}
                                        className={`doc-card ${expandedDoc === doc.id ? 'expanded' : ''}`}
                                        onClick={() => setExpandedDoc(expandedDoc === doc.id ? null : doc.id)}
                                    >
                                        <div className="doc-card-header">
                                            <div className="doc-icon">{Icons.file}</div>
                                            <div className="doc-info">
                                                <div className="doc-name" title={doc.filename}>{doc.filename}</div>
                                                <div className="doc-type">{doc.file_type?.toUpperCase() || 'FILE'}</div>
                                            </div>
                                        </div>

                                        {/* Summary Section */}
                                        {renderSummary(doc)}

                                        <div className="doc-card-meta">
                                            <div className="meta-item">
                                                {Icons.calendar}
                                                <span>{formatDate(doc.upload_date)}</span>
                                            </div>
                                            <div className="meta-item">
                                                <span>{formatSize(doc.file_size)}</span>
                                            </div>
                                            <span className={`doc-status ${doc.status}`}>
                                                {doc.status === 'processed' ? 'Ready' :
                                                    doc.status === 'processing' ? 'Processing' :
                                                        doc.status === 'error' ? 'Error' : 'Unknown'}
                                            </span>
                                        </div>
                                        <div className="doc-card-actions">
                                            {(!doc.summary && doc.summary_status !== 'generating') && (
                                                <button
                                                    className="generate-btn"
                                                    onClick={(e) => {
                                                        e.stopPropagation();
                                                        handleGenerateSummary(doc.id);
                                                    }}
                                                    disabled={generatingId === doc.id}
                                                >
                                                    {Icons.sparkle}
                                                    <span>{generatingId === doc.id ? 'Generating...' : 'Generate Summary'}</span>
                                                </button>
                                            )}
                                            <button
                                                className="delete-btn"
                                                onClick={(e) => {
                                                    e.stopPropagation();
                                                    handleDelete(doc.id);
                                                }}
                                                disabled={deletingId === doc.id}
                                            >
                                                {Icons.trash}
                                                <span>{deletingId === doc.id ? 'Deleting...' : 'Delete'}</span>
                                            </button>
                                        </div>
                                    </div>
                                ))}
                            </div>
                        ) : (
                            <div className="docs-list">
                                {filtered.map(doc => (
                                    <div
                                        key={doc.id}
                                        className={`doc-list-item ${expandedDoc === doc.id ? 'expanded' : ''}`}
                                        onClick={() => setExpandedDoc(expandedDoc === doc.id ? null : doc.id)}
                                    >
                                        <div className="doc-list-main">
                                            <div className="doc-icon">{Icons.file}</div>
                                            <div className="doc-info">
                                                <div className="doc-name">{doc.filename}</div>
                                                <div className="doc-type">{doc.file_type?.toUpperCase() || 'FILE'}</div>
                                            </div>
                                            <div className="doc-list-meta">
                                                <div className="meta-item">
                                                    {Icons.calendar}
                                                    <span>{formatDate(doc.upload_date)}</span>
                                                </div>
                                                <div className="meta-item">
                                                    <span>{formatSize(doc.file_size)}</span>
                                                </div>
                                                <span className={`doc-status ${doc.status}`}>
                                                    {doc.status === 'processed' ? 'Ready' :
                                                        doc.status === 'processing' ? 'Processing' : 'Error'}
                                                </span>
                                            </div>
                                            <button
                                                className="delete-btn"
                                                onClick={(e) => {
                                                    e.stopPropagation();
                                                    handleDelete(doc.id);
                                                }}
                                                disabled={deletingId === doc.id}
                                            >
                                                {Icons.trash}
                                            </button>
                                        </div>
                                        {/* Summary in list view */}
                                        {doc.summary && (
                                            <div className="doc-list-summary">
                                                <span className="summary-label">{Icons.sparkle} Summary:</span>
                                                <span className="summary-text">{doc.summary}</span>
                                            </div>
                                        )}
                                    </div>
                                ))}
                            </div>
                        )}
            </div>
        </div>
    );
}
