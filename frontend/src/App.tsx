import { useState } from 'react'
import ProjectList from './components/ProjectList'
import ProjectUploader from './components/ProjectUploader'

export default function App() {
  const [refreshKey, setRefreshKey] = useState(0)

  return (
    <main>
      <h1>RepoLens dashboard</h1>
      <ProjectUploader onUploaded={() => setRefreshKey((value) => value + 1)} />
      <ProjectList refreshKey={refreshKey} />
    </main>
  )
}
