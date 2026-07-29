import type {
  HealthResponse,
  IndexStartResponse,
  ProjectCreatedResponse,
  ProjectRecord,
  SourceResponse,
  SourceSummary,
} from '../types/api'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000/api'

export async function getHealth(): Promise<HealthResponse> {
  const response = await fetch(`${API_BASE_URL}/health`)
  if (!response.ok) {
    throw new Error('Failed to fetch health endpoint')
  }
  return response.json()
}

export async function uploadProject(file: File): Promise<ProjectCreatedResponse> {
  const formData = new FormData()
  formData.append('file', file)

  const response = await fetch(`${API_BASE_URL}/projects`, {
    method: 'POST',
    body: formData,
  })
  if (!response.ok) {
    const body = await response.json().catch(() => null)
    throw new Error(body?.detail || 'Upload failed')
  }
  return response.json()
}

export async function getProjects(): Promise<ProjectRecord[]> {
  const response = await fetch(`${API_BASE_URL}/projects`)
  if (!response.ok) {
    throw new Error('Failed to load projects')
  }
  return response.json()
}

export async function getProject(projectId: string): Promise<ProjectRecord> {
  const response = await fetch(`${API_BASE_URL}/projects/${encodeURIComponent(projectId)}`)
  if (!response.ok) {
    throw new Error('Failed to load project')
  }
  return response.json()
}

export async function indexProject(projectId: string): Promise<IndexStartResponse> {
  const response = await fetch(
    `${API_BASE_URL}/projects/${encodeURIComponent(projectId)}/index`,
    { method: 'POST' },
  )
  if (!response.ok) {
    const body = await response.json().catch(() => null)
    throw new Error(body?.detail || 'Indexing failed to start')
  }
  return response.json()
}

export async function getProjectChunks(projectId: string): Promise<SourceSummary[]> {
  const response = await fetch(
    `${API_BASE_URL}/projects/${encodeURIComponent(projectId)}/chunks`,
  )
  if (!response.ok) {
    throw new Error('Failed to load source chunks')
  }
  return response.json()
}

export async function getSourceChunk(
  projectId: string,
  chunkId: string,
): Promise<SourceResponse> {
  const response = await fetch(
    `${API_BASE_URL}/projects/${encodeURIComponent(projectId)}/chunks/${encodeURIComponent(chunkId)}`,
  )
  if (!response.ok) {
    throw new Error('Failed to load source chunk')
  }
  return response.json()
}
