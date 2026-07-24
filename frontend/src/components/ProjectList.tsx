import { useEffect, useState } from 'react'

interface ProjectRecord {
  id: string
  name: string
  status: string
  created_at: string
}

interface ProjectListProps {
  refreshKey: number
}

export default function ProjectList({ refreshKey }: ProjectListProps) {
  const [projects, setProjects] = useState<ProjectRecord[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    async function loadProjects() {
      setIsLoading(true)
      setError(null)

      try {
        const response = await fetch('http://127.0.0.1:8000/api/projects')
        if (!response.ok) {
          throw new Error('Failed to load projects')
        }
        const data = (await response.json()) as ProjectRecord[]
        setProjects(data)
      } catch (loadError) {
        setError(loadError instanceof Error ? loadError.message : 'Failed to load projects')
      } finally {
        setIsLoading(false)
      }
    }

    loadProjects()
  }, [refreshKey])

  if (isLoading) {
    return <p>Loading projects…</p>
  }

  if (error) {
    return <p role="alert">{error}</p>
  }

  return (
    <section>
      <h2>Projects</h2>
      {projects.length === 0 ? (
        <p>No projects yet.</p>
      ) : (
        <ul>
          {projects.map((project) => (
            <li key={project.id}>
              <strong>{project.name}</strong>
              <div>Status: {project.status}</div>
              <div>Created: {new Date(project.created_at).toLocaleString()}</div>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}
