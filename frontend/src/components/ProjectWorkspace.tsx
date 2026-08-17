import { useEffect, useState } from 'react'
import {
  getProject,
  getProjectChunks,
  getSourceChunk,
  indexProject,
} from '../api/client'
import type { ProjectRecord, SourceResponse, SourceSummary } from '../types/api'
import ChatPanel from './ChatPanel'
import SourceViewer from './SourceViewer'
import { formatDate, statusLabel } from './ProjectList'

interface ProjectWorkspaceProps {
  projectId: string | null
  onProjectChanged: () => void
}

const POLL_INTERVAL_MS = 1000
const POLL_TIMEOUT_MS = 3 * 60 * 1000

export default function ProjectWorkspace({
  projectId,
  onProjectChanged,
}: ProjectWorkspaceProps) {
  const [project, setProject] = useState<ProjectRecord | null>(null)
  const [chunks, setChunks] = useState<SourceSummary[]>([])
  const [selectedSource, setSelectedSource] = useState<SourceResponse | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [isIndexStarting, setIsIndexStarting] = useState(false)
  const [isSourceLoading, setIsSourceLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    setSelectedSource(null)
    setChunks([])
    setProject(null)

    if (!projectId) return

    async function loadWorkspace() {
      setIsLoading(true)
      setError(null)
      try {
        const loadedProject = await getProject(projectId as string)
        if (cancelled) return
        setProject(loadedProject)
        if (loadedProject.status === 'indexed') {
          const loadedChunks = await getProjectChunks(projectId as string)
          if (!cancelled) setChunks(loadedChunks)
        }
      } catch (loadError) {
        if (!cancelled) {
          setError(loadError instanceof Error ? loadError.message : 'Proje yüklenemedi.')
        }
      } finally {
        if (!cancelled) setIsLoading(false)
      }
    }

    loadWorkspace()
    return () => {
      cancelled = true
    }
  }, [projectId])

  useEffect(() => {
    if (!projectId || project?.status !== 'indexing') return

    let cancelled = false
    let timer: number | undefined
    const deadline = Date.now() + POLL_TIMEOUT_MS

    async function pollStatus() {
      try {
        if (Date.now() >= deadline) {
          setError('İndeksleme beklenenden uzun sürüyor. Durumu tekrar kontrol etmek için sayfayı yenileyebilirsin.')
          return
        }
        const updatedProject = await getProject(projectId as string)
        if (cancelled) return

        if (updatedProject.status === 'indexing') {
          setProject(updatedProject)
          timer = window.setTimeout(pollStatus, POLL_INTERVAL_MS)
          return
        }

        if (updatedProject.status === 'indexed') {
          const loadedChunks = await getProjectChunks(projectId as string)
          if (cancelled) return
          setChunks(loadedChunks)
        }
        setProject(updatedProject)
        if (updatedProject.status === 'failed') {
          setError(updatedProject.error_message || 'İndeksleme başarısız oldu.')
        }
        onProjectChanged()
      } catch (pollError) {
        if (!cancelled) {
          setError(pollError instanceof Error ? pollError.message : 'İndeks durumu alınamadı.')
        }
      }
    }

    timer = window.setTimeout(pollStatus, POLL_INTERVAL_MS)
    return () => {
      cancelled = true
      if (timer) window.clearTimeout(timer)
    }
  }, [projectId, project?.status, onProjectChanged])

  async function handleIndex() {
    if (!projectId) return
    setIsIndexStarting(true)
    setError(null)
    setSelectedSource(null)
    try {
      await indexProject(projectId)
      setChunks([])
      setProject((current) => current ? { ...current, status: 'indexing' } : current)
      onProjectChanged()
    } catch (indexError) {
      setError(indexError instanceof Error ? indexError.message : 'İndeksleme başlatılamadı.')
    } finally {
      setIsIndexStarting(false)
    }
  }

  async function handleOpenSource(chunkId: string) {
    if (!projectId) return
    setIsSourceLoading(true)
    setError(null)
    try {
      setSelectedSource(await getSourceChunk(projectId, chunkId))
    } catch (sourceError) {
      setError(sourceError instanceof Error ? sourceError.message : 'Kaynak yüklenemedi.')
    } finally {
      setIsSourceLoading(false)
    }
  }

  if (!projectId) {
    return (
      <section className="panel workspace-panel empty-state">
        <span className="empty-state__icon" aria-hidden="true">⌘</span>
        <h2>Bir proje seç</h2>
        <p>Detayları görmek veya soru sormak için soldan bir proje seç.</p>
      </section>
    )
  }

  if (isLoading || !project) {
    if (error && !isLoading) {
      return <section className="panel workspace-panel empty-state"><h2>Proje açılamadı</h2><p role="alert">{error}</p></section>
    }
    return <section className="panel workspace-panel loading-state" role="status"><span className="spinner" /> Proje hazırlanıyor</section>
  }

  const isIndexing = project.status === 'indexing'
  const isIndexed = project.status === 'indexed'

  return (
    <section className="panel workspace-panel">
      <header className="workspace-header">
        <div className="workspace-title">
          <p className="eyebrow">SEÇİLİ PROJE</p>
          <h2>{project.display_name}</h2>
          <p>{formatDate(project.created_at)} tarihinde yüklendi</p>
        </div>
        <div className="workspace-actions">
          <span className={`status-pill status-pill--${project.status}`}>
            <span /> {statusLabel(project.status)}
          </span>
          <button
            className="button button--secondary"
            type="button"
            onClick={handleIndex}
            disabled={isIndexing || isIndexStarting}
          >
            {isIndexing || isIndexStarting ? <><span className="spinner" /> İndeksleniyor</> : isIndexed ? 'Yeniden indeksle' : 'İndeksle'}
          </button>
        </div>
      </header>

      <div className="project-stats">
        <div><strong>{project.file_count}</strong><span>Kaynak dosya</span></div>
        <div><strong>{project.chunk_count}</strong><span>İndeksli parça</span></div>
        <div><strong>{project.indexed_at ? formatDate(project.indexed_at) : '—'}</strong><span>Son indeks</span></div>
      </div>

      {isIndexing ? (
        <div className="indexing-banner" role="status">
          <span className="spinner" />
          <div><strong>Proje yerel olarak indeksleniyor</strong><p>Dosyalar ayrıştırılıyor ve embedding’ler hazırlanıyor. Bu ekran otomatik güncellenecek.</p></div>
        </div>
      ) : null}
      {error ? <p className="form-message form-message--error" role="alert">{error}</p> : null}
      {isSourceLoading ? <p className="loading-inline" role="status"><span className="spinner" /> Kaynak açılıyor</p> : null}

      <ChatPanel
        projectId={projectId}
        disabled={!isIndexed}
        onSelectSource={handleOpenSource}
      />

      <section className="workspace-section sources-section" aria-labelledby="sources-title">
        <div className="section-heading">
          <div><p className="eyebrow">SOURCE VIEWER</p><h3 id="sources-title">İndekslenen kaynaklar</h3></div>
          <span className="count-badge">{chunks.length}</span>
        </div>
        {!isIndexed ? (
          <p className="muted-copy">Kaynakları görmek için projeyi indeksle.</p>
        ) : chunks.length === 0 ? (
          <div className="empty-state empty-state--compact"><strong>İndekslenebilir parça bulunamadı</strong><p>Desteklenen Python fonksiyonları, sınıfları veya Markdown bölümleri görünmüyor.</p></div>
        ) : (
          <div className="source-browser">
            {chunks.map((chunk) => (
              <button className="source-row" type="button" key={chunk.chunk_id} onClick={() => handleOpenSource(chunk.chunk_id)}>
                <span className={`language-icon language-icon--${chunk.language}`}>{chunk.language === 'python' ? 'PY' : 'MD'}</span>
                <span><strong>{chunk.file_path}</strong><small>{chunk.symbol_name ?? chunk.symbol_type}</small></span>
                <span className="line-range">L{chunk.start_line}–{chunk.end_line}</span>
              </button>
            ))}
          </div>
        )}
      </section>

      {selectedSource ? <SourceViewer source={selectedSource} onClose={() => setSelectedSource(null)} /> : null}
    </section>
  )
}
