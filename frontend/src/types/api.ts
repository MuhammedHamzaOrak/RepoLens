export interface HealthResponse {
  status: string
  service: string
}

export interface ProjectRecord {
  id: string
  display_name: string
  status: string
  created_at: string
  indexed_at: string | null
  file_count: number
  chunk_count: number
  error_message: string | null
}

export interface ProjectCreatedResponse {
  project_id: string
  filename: string
}

export interface IndexStartResponse {
  project_id: string
  status: string
}

export interface SourceSummary {
  chunk_id: string
  file_path: string
  language: string
  symbol_name: string | null
  symbol_type: string
  start_line: number
  end_line: number
  parse_status: string
}

export interface SourceResponse extends SourceSummary {
  score: number | null
  snippet: string
}

export type AnswerStatus =
  | 'grounded'
  | 'insufficient_context'
  | 'indexing_incomplete'
  | 'error'

export interface ChatResponse {
  answer: string
  answer_status: AnswerStatus
  sources: SourceResponse[]
}

export interface ChatHistoryMessage {
  role: 'user' | 'assistant'
  content: string
}
