import { useEffect, useState } from 'react'
import {
  getProject,
  getProjectChunks,
  getProjects,
  getSourceChunk,
  indexProject,
} from '../api/client'
import type { ProjectRecord, SourceResponse, SourceSummary } from '../types/api'
import SourceViewer from './SourceViewer'

interface ProjectListProps {
  refreshKey: number
}

const POLL_INTERVAL_MS = 1000
const POLL_TIMEOUT_MS = 3 * 60 * 1000

function delay(milliseconds: number) {
  return new Promise((resolve) => window.setTimeout(resolve, milliseconds))
}

export default function ProjectList({ refreshKey }: ProjectListProps) {
  const [projects, setProjects] = useState<ProjectRecord[]>([])
  const [chunksByProject, setChunksByProject] = useState<Record<string, SourceSummary[]>>({})
  const [selectedSource, setSelectedSource] = useState<SourceResponse | null>(null)
  const [busyProjectId, setBusyProjectId] = useState<string | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    async function loadProjects() {
      setIsLoading(true)
      setError(null)

      try {
        setProjects(await getProjects())
      } catch (loadError) {
        setError(loadError instanceof Error ? loadError.message : 'Failed to load projects')
      } finally {
        setIsLoading(false)
      }
    }

    loadProjects()
  }, [refreshKey])

  function replaceProject(updatedProject: ProjectRecord) {
    setProjects((current) =>
      current.map((project) =>
        project.id === updatedProject.id ? updatedProject : project,
      ),
    )
  }

  async function waitForIndex(projectId: string): Promise<ProjectRecord> {
    const deadline = Date.now() + POLL_TIMEOUT_MS

    while (Date.now() < deadline) {
      const project = await getProject(projectId)
      replaceProject(project)
      if (project.status !== 'indexing') {
        return project
      }
      await delay(POLL_INTERVAL_MS)
    }
    throw new Error(
      'Indexing is taking longer than expected. Refresh the page to check again.',
    )
  }

  async function handleIndex(projectId: string) {
    setBusyProjectId(projectId)
    setError(null)
    setSelectedSource(null)

    try {
      await indexProject(projectId)
      const project = await waitForIndex(projectId)
      if (project.status === 'failed') {
        throw new Error(project.error_message || 'Indexing failed')
      }
      const chunks = await getProjectChunks(projectId)
      setChunksByProject((current) => ({
        ...current,
        [projectId]: chunks,
      }))
    } catch (indexError) {
      setError(indexError instanceof Error ? indexError.message : 'Indexing failed')
    } finally {
      setBusyProjectId(null)
    }
  }

  async function handleShowChunks(projectId: string) {
    setBusyProjectId(projectId)
    setError(null)
    try {
      const chunks = await getProjectChunks(projectId)
      setChunksByProject((current) => ({
        ...current,
        [projectId]: chunks,
      }))
    } catch (chunkError) {
      setError(chunkError instanceof Error ? chunkError.message : 'Failed to load chunks')
    } finally {
      setBusyProjectId(null)
    }
  }

  async function handleViewSource(projectId: string, chunkId: string) {
    setError(null)
    try {
      setSelectedSource(await getSourceChunk(projectId, chunkId))
    } catch (sourceError) {
      setError(sourceError instanceof Error ? sourceError.message : 'Failed to load source')
    }
  }

  if (isLoading) {
    return <p>Loading projects…</p>
  }

  return (
    <>
      {error ? <p role="alert">{error}</p> : null}
      <section>
        <h2>Projects</h2>
        {projects.length === 0 ? (
          <p>No projects yet.</p>
        ) : (
          <ul className="project-list">
            {projects.map((project) => {
              const chunks = chunksByProject[project.id]
              const isBusy = busyProjectId === project.id

              return (
                <li className="project-card" key={project.id}>
                  <strong>{project.display_name}</strong>
                  <div>Status: {project.status}</div>
                  <div>Created: {new Date(project.created_at).toLocaleString()}</div>
                  <div>
                    Files: {project.file_count} · Chunks: {project.chunk_count}
                  </div>
                  <div className="project-card__actions">
                    <button
                      type="button"
                      disabled={isBusy || project.status === 'indexing'}
                      onClick={() => handleIndex(project.id)}
                    >
                      {isBusy ? 'Working…' : project.status === 'indexed' ? 'Re-index' : 'Index'}
                    </button>
                    {project.status === 'indexed' ? (
                      <button
                        type="button"
                        disabled={isBusy}
                        onClick={() => handleShowChunks(project.id)}
                      >
                        Show chunks
                      </button>
                    ) : null}
                  </div>
                  {chunks ? (
                    chunks.length === 0 ? (
                      <p>No supported source chunks were found.</p>
                    ) : (
                      <ul className="chunk-list">
                        {chunks.map((chunk) => (
                          <li key={chunk.chunk_id}>
                            <button
                              type="button"
                              onClick={() => handleViewSource(project.id, chunk.chunk_id)}
                            >
                              {chunk.file_path}:{chunk.start_line}–{chunk.end_line}
                              {chunk.symbol_name ? ` · ${chunk.symbol_name}` : ''}
                            </button>
                          </li>
                        ))}
                      </ul>
                    )
                  ) : null}
                </li>
              )
            })}
          </ul>
        )}
      </section>
      {selectedSource ? (
        <SourceViewer source={selectedSource} onClose={() => setSelectedSource(null)} />
      ) : null}
    </>
  )
}
