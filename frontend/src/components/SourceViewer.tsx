import { useEffect } from 'react'
import type { SourceResponse } from '../types/api'

interface SourceViewerProps {
  source: SourceResponse
  onClose: () => void
}

export default function SourceViewer({ source, onClose }: SourceViewerProps) {
  useEffect(() => {
    function closeOnEscape(event: KeyboardEvent) {
      if (event.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', closeOnEscape)
    return () => window.removeEventListener('keydown', closeOnEscape)
  }, [onClose])

  return (
    <div className="source-overlay" role="presentation" onMouseDown={(event) => {
      if (event.target === event.currentTarget) onClose()
    }}>
      <section className="source-viewer" role="dialog" aria-modal="true" aria-labelledby="source-title">
        <header className="source-viewer__header">
          <div>
            <p className="eyebrow">KAYNAK KOD</p>
            <h2 id="source-title">{source.file_path}</h2>
            <p>
              {source.symbol_name ?? source.symbol_type} · satır {source.start_line}–{source.end_line} · {source.language}
            </p>
          </div>
          <button className="icon-button" type="button" onClick={onClose} aria-label="Kaynağı kapat">×</button>
        </header>
        <div className="code-view" tabIndex={0}>
          <pre><code>{source.snippet}</code></pre>
        </div>
        <footer className="source-viewer__footer">
          <span>Parse durumu: {source.parse_status}</span>
          <span>Chunk: {source.chunk_id.slice(0, 8)}</span>
        </footer>
      </section>
    </div>
  )
}
