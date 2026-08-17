import { useEffect, useState } from 'react'
import { getProjects } from '../api/client'
import type { ProjectRecord } from '../types/api'

interface ProjectListProps {
  refreshKey: number
  selectedProjectId: string | null
  onSelectProject: (projectId: string | null) => void
}

const STATUS_LABELS: Record<string, string> = {
  uploading: 'Yükleniyor',
  ready_to_index: 'İndeks bekliyor',
  indexing: 'İndeksleniyor',
  indexed: 'Hazır',
  failed: 'Başarısız',
}

export function statusLabel(status: string) {
  return STATUS_LABELS[status] ?? status
}

export function formatDate(value: string) {
  return new Intl.DateTimeFormat('tr-TR', {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(new Date(value))
}

export default function ProjectList({
  refreshKey,
  selectedProjectId,
  onSelectProject,
}: ProjectListProps) {
  const [projects, setProjects] = useState<ProjectRecord[]>([])
  const [requestKey, setRequestKey] = useState(0)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false

    async function loadProjects() {
      setIsLoading(true)
      setError(null)
      try {
        const loadedProjects = await getProjects()
        if (cancelled) return
        setProjects(loadedProjects)

        const selectionExists = loadedProjects.some(
          (project) => project.id === selectedProjectId,
        )
        if (!selectionExists) {
          onSelectProject(loadedProjects[0]?.id ?? null)
        }
      } catch (loadError) {
        if (!cancelled) {
          setError(
            loadError instanceof Error ? loadError.message : 'Projeler yüklenemedi.',
          )
        }
      } finally {
        if (!cancelled) setIsLoading(false)
      }
    }

    loadProjects()
    return () => {
      cancelled = true
    }
  }, [refreshKey, requestKey, selectedProjectId, onSelectProject])

  return (
    <aside className="panel project-sidebar" aria-label="Projeler">
      <div className="panel-heading">
        <div>
          <p className="eyebrow">ÇALIŞMA ALANI</p>
          <h2>Projeler</h2>
        </div>
        <span className="count-badge">{projects.length}</span>
      </div>

      {isLoading ? (
        <div className="loading-state" role="status"><span className="spinner" /> Projeler yükleniyor</div>
      ) : error ? (
        <div className="inline-error" role="alert">
          <p>{error}</p>
          <button className="text-button" type="button" onClick={() => setRequestKey((value) => value + 1)}>
            Tekrar dene
          </button>
        </div>
      ) : projects.length === 0 ? (
        <div className="empty-state empty-state--compact">
          <span aria-hidden="true">⌁</span>
          <strong>Henüz proje yok</strong>
          <p>İlk ZIP dosyanı yukarıdan yükleyerek başla.</p>
        </div>
      ) : (
        <ul className="project-list">
          {projects.map((project) => (
            <li key={project.id}>
              <button
                className={`project-item${selectedProjectId === project.id ? ' is-selected' : ''}`}
                type="button"
                onClick={() => onSelectProject(project.id)}
              >
                <span className="project-item__topline">
                  <strong title={project.display_name}>{project.display_name}</strong>
                  <span className={`status-dot status-dot--${project.status}`} aria-hidden="true" />
                </span>
                <span className="project-item__meta">
                  {statusLabel(project.status)} · {formatDate(project.created_at)}
                </span>
                <span className="project-item__stats">
                  <span>{project.file_count} dosya</span>
                  <span>{project.chunk_count} parça</span>
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </aside>
  )
}
