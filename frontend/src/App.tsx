import { Route, Routes } from 'react-router-dom'

import { AppLayout } from './layouts/AppLayout'
import { AdvisoryAssistant } from './pages/AdvisoryAssistant'
import { Evaluation } from './pages/Evaluation'
import { Home } from './pages/Home'
import { KnowledgeBase } from './pages/KnowledgeBase'
import { ProjectInfo } from './pages/ProjectInfo'
import { SafetyGuidelines } from './pages/SafetyGuidelines'

function App() {
  return (
    <Routes>
      <Route element={<AppLayout />}>
        <Route index element={<Home />} />
        <Route path="advisory" element={<AdvisoryAssistant />} />
        <Route path="knowledge-base" element={<KnowledgeBase />} />
        <Route path="safety-guidelines" element={<SafetyGuidelines />} />
        <Route path="project-info" element={<ProjectInfo />} />
        <Route path="evaluation" element={<Evaluation />} />
        {/* The pre-redesign dashboard lived here; keep old links working. */}
        <Route path="dashboard" element={<Home />} />
      </Route>
    </Routes>
  )
}

export default App

