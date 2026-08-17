import { useState } from 'react'
import { uploadProject } from '../api/client'

interface ProjectUploaderProps {
  onUploaded: (projectId: string) => void
}

export default function ProjectUploader({ onUploaded }: ProjectUploaderProps) {
  const [file, setFile] = useState<File | null>(null)
  const [isUploading, setIsUploading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)
  const [inputKey, setInputKey] = useState(0)

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!file) {
      setError('Önce bir ZIP dosyası seçmelisin.')
      return
    }

    setIsUploading(true)
    setError(null)
    setSuccess(null)

    try {
      const created = await uploadProject(file)
      setFile(null)
      setInputKey((value) => value + 1)
      setSuccess(`${created.filename} yüklendi. Şimdi indeksleyebilirsin.`)
      onUploaded(created.project_id)
    } catch (uploadError) {
      setError(uploadError instanceof Error ? uploadError.message : 'Proje yüklenemedi.')
    } finally {
      setIsUploading(false)
    }
  }

  return (
    <div className="upload-panel">
      <form onSubmit={handleSubmit} className="upload-form">
        <label className="file-picker">
          <span className="file-picker__icon" aria-hidden="true">↑</span>
          <span>
            <strong>{file ? file.name : 'ZIP dosyası seç'}</strong>
            <small>{file ? 'Dosyayı değiştirmek için tıkla' : 'Python ve Markdown projeleri'}</small>
          </span>
          <input
            key={inputKey}
            type="file"
            accept=".zip,application/zip"
            onChange={(event) => {
              setFile(event.target.files?.[0] ?? null)
              setError(null)
              setSuccess(null)
            }}
          />
        </label>
        <button className="button button--primary" type="submit" disabled={isUploading}>
          {isUploading ? <><span className="spinner" /> Yükleniyor</> : 'Projeyi yükle'}
        </button>
      </form>
      {error ? <p className="form-message form-message--error" role="alert">{error}</p> : null}
      {success ? <p className="form-message form-message--success" role="status">{success}</p> : null}
    </div>
  )
}
