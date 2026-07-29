import { useState } from 'react'
import { uploadProject } from '../api/client'

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

    try {
      await uploadProject(file)
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
          {isUploading ? 'Uploading…' : 'Upload project'}
        </button>
      </form>
      {error ? <p role="alert">{error}</p> : null}
    </section>
  )
}
