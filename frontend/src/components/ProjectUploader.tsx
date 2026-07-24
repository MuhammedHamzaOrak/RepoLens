import { useState } from 'react'

interface ProjectUploaderProps {
  onUploaded: () => void
}

export default function ProjectUploader({ onUploaded }: ProjectUploaderProps) {
  const [file, setFile] = useState<File | null>(null)
  const [isUploading, setIsUploading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!file) {
      setError('Please select a ZIP file first.')
      return
    }

    setIsUploading(true)
    setError(null)

    const formData = new FormData()
    formData.append('file', file)

    try {
      const response = await fetch('http://127.0.0.1:8000/api/projects', {
        method: 'POST',
        body: formData,
      })

      if (!response.ok) {
        const detail = await response.json().catch(() => null)
        throw new Error(detail?.detail || 'Upload failed')
      }

      setFile(null)
      onUploaded()
    } catch (uploadError) {
      setError(uploadError instanceof Error ? uploadError.message : 'Upload failed')
    } finally {
      setIsUploading(false)
    }
  }

  return (
    <section>
      <h2>Upload project</h2>
      <form onSubmit={handleSubmit}>
        <input
          type="file"
          accept=".zip"
          onChange={(event) => setFile(event.target.files?.[0] ?? null)}
        />
        <button type="submit" disabled={isUploading}>
          {isUploading ? 'Uploading…' : 'Yükle ve indeksle'}
        </button>
      </form>
      {error ? <p role="alert">{error}</p> : null}
    </section>
  )
}
