import { Routes, Route } from 'react-router-dom'
import Dashboard from './pages/Dashboard'
import Workflow from './pages/Workflow'
import SettingsPage from './pages/SettingsPage'

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Dashboard />} />
      <Route path="/workflow/:projectId" element={<Workflow />} />
      <Route path="/settings" element={<SettingsPage />} />
    </Routes>
  )
}
