import './CitationBadge.css'

function CitationBadge({ sources, onSourceClick }) {
  if (!sources || sources.length === 0) {
    return null
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

  return (
    <div className="citation-badges">
      <span className="citation-label">Sources:</span>
      {sources.map((source, index) => (
        <button
          key={source.id || index}
          className="citation-badge"
          onClick={() => onSourceClick && onSourceClick(source)}
          title={`View ${source.filename}`}
        >
          <span className="citation-icon">{getFileIcon(source.file_type)}</span>
          <span className="citation-filename">
            {source.filename.length > 20
              ? source.filename.substring(0, 20) + '...'
              : source.filename}
          </span>
        </button>
      ))}
    </div>
  )
}

export default CitationBadge

