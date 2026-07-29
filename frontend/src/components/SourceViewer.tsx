import type { SourceResponse } from '../types/api'

interface SourceViewerProps {
  source: SourceResponse
  onClose: () => void
}

export default function SourceViewer({ source, onClose }: SourceViewerProps) {
  return (
    <section className="source-viewer" aria-label="Source viewer">
      <div className="source-viewer__header">
        <div>
          <strong>{source.file_path}</strong>
          <div>
            {source.symbol_name ?? source.symbol_type} · lines {source.start_line}–
            {source.end_line}
          </div>
        </div>
        <button type="button" onClick={onClose}>
          Close
        </button>
      </div>
      <pre>
        <code>{source.snippet}</code>
      </pre>
    </section>
  )
}
