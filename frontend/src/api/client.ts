import type {
  ChatResponse,
  HealthResponse,
  IndexStartResponse,
  ProjectCreatedResponse,
  ProjectRecord,
  SourceResponse,
  SourceSummary,
} from '../types/api'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000/api'

async function readResponse<T>(response: Response, fallbackMessage: string): Promise<T> {
  const body = await response.json().catch(() => null)
  if (!response.ok) {
    throw new Error(body?.detail || body?.answer || fallbackMessage)
  }
  return body as T
}

export async function getHealth(): Promise<HealthResponse> {
  const response = await fetch(`${API_BASE_URL}/health`)
  return readResponse(response, 'Backend bağlantısı kurulamadı.')
}

export async function uploadProject(file: File): Promise<ProjectCreatedResponse> {
  const formData = new FormData()
  formData.append('file', file)

  const response = await fetch(`${API_BASE_URL}/projects`, {
    method: 'POST',
    body: formData,
  })
  return readResponse(response, 'Proje yüklenemedi.')
}

export async function getProjects(): Promise<ProjectRecord[]> {
  const response = await fetch(`${API_BASE_URL}/projects`)
  return readResponse(response, 'Projeler yüklenemedi.')
}

export async function getProject(projectId: string): Promise<ProjectRecord> {
  const response = await fetch(`${API_BASE_URL}/projects/${encodeURIComponent(projectId)}`)
  return readResponse(response, 'Proje bilgileri yüklenemedi.')
}

export async function indexProject(projectId: string): Promise<IndexStartResponse> {
  const response = await fetch(
    `${API_BASE_URL}/projects/${encodeURIComponent(projectId)}/index`,
    { method: 'POST' },
  )
  return readResponse(response, 'İndeksleme başlatılamadı.')
}

export async function getProjectChunks(projectId: string): Promise<SourceSummary[]> {
  const response = await fetch(
    `${API_BASE_URL}/projects/${encodeURIComponent(projectId)}/chunks`,
  )
  return readResponse(response, 'Kaynaklar yüklenemedi.')
}

export async function getSourceChunk(
  projectId: string,
  chunkId: string,
): Promise<SourceResponse> {
  const response = await fetch(
    `${API_BASE_URL}/projects/${encodeURIComponent(projectId)}/chunks/${encodeURIComponent(chunkId)}`,
  )
  return readResponse(response, 'Kaynak kod yüklenemedi.')
}

export async function askProject(
  projectId: string,
  question: string,
): Promise<ChatResponse> {
  const response = await fetch(
    `${API_BASE_URL}/projects/${encodeURIComponent(projectId)}/chat`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question }),
    },
  )
  return readResponse(response, 'Yanıt oluşturulamadı.')
}
