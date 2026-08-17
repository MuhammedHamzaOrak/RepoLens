import { useCallback, useState } from 'react'
import ProjectList from './components/ProjectList'
import ProjectUploader from './components/ProjectUploader'
import ProjectWorkspace from './components/ProjectWorkspace'

export default function App() {
  const [refreshKey, setRefreshKey] = useState(0)
  const [selectedProjectId, setSelectedProjectId] = useState<string | null>(null)

  const selectProject = useCallback((projectId: string | null) => {
    setSelectedProjectId(projectId)
  }, [])

  const refreshProjects = useCallback(() => {
    setRefreshKey((value) => value + 1)
  }, [])

  function handleUploaded(projectId: string) {
    setSelectedProjectId(projectId)
    setRefreshKey((value) => value + 1)
  }

  return (
    <div className="app-shell">
      <header className="app-header">
        <div className="brand-mark" aria-hidden="true">RL</div>
        <div>
          <p className="eyebrow">LOCAL-FIRST CODE INTELLIGENCE</p>
          <h1>RepoLens</h1>
        </div>
        <span className="local-badge"><span /> Tamamen yerel</span>
      </header>

      <main>
        <section className="hero-copy">
          <div>
            <h2>Kod tabanını kaynaklarıyla birlikte keşfet.</h2>
            <p>
              Python veya Markdown projesini yükle, yerel olarak indeksle ve
              cevapların hangi koddan geldiğini anında gör.
            </p>
          </div>
          <ProjectUploader onUploaded={handleUploaded} />
        </section>

        <div className="dashboard-grid">
          <ProjectList
            refreshKey={refreshKey}
            selectedProjectId={selectedProjectId}
            onSelectProject={selectProject}
          />
          <ProjectWorkspace
            projectId={selectedProjectId}
            onProjectChanged={refreshProjects}
          />
        </div>
      </main>
    </div>
  )
}
