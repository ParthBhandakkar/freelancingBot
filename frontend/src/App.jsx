import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import Layout from './components/Layout'
import { ToastProvider } from './components/Toast'
import Dashboard from './pages/Dashboard'
import Leads from './pages/Leads'
import LeadDetail from './pages/LeadDetail'
import Search from './pages/Search'
import Outreach from './pages/Outreach'
import Settings from './pages/Settings'
import Today from './pages/Today'
import Pipeline from './pages/Pipeline'

export default function App() {
  return (
    <BrowserRouter>
      <ToastProvider>
        <Routes>
          <Route element={<Layout />}>
            <Route path="/" element={<Navigate to="/today" replace />} />
            <Route path="/today" element={<Today />} />
            <Route path="/dashboard" element={<Dashboard />} />
            <Route path="/leads" element={<Leads />} />
            <Route path="/leads/:id" element={<LeadDetail />} />
            <Route path="/pipeline" element={<Pipeline />} />
            <Route path="/search" element={<Search />} />
            <Route path="/outreach" element={<Outreach />} />
            <Route path="/settings" element={<Settings />} />
          </Route>
        </Routes>
      </ToastProvider>
    </BrowserRouter>
  )
}
