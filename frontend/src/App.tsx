import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import Layout from './components/common/Layout'
import Dashboard from './pages/Dashboard'
import DepartmentDetail from './pages/DepartmentDetail'
import Recommendation from './pages/Recommendation'
import Risk from './pages/Risk'
import DataManagement from './pages/DataManagement'


function App() {
  return (
    <BrowserRouter>
      <Layout>
        <Routes>
          <Route path="/" element={<Navigate to="/dashboard" replace />} />
          <Route path="/dashboard" element={<Dashboard />} />
          <Route path="/department" element={<DepartmentDetail />} />
          <Route path="/recommendation" element={<Recommendation />} />
          <Route path="/risk" element={<Risk />} />
          <Route path="/dataManagement" element={<DataManagement />} />
        </Routes>
      </Layout>
    </BrowserRouter>
  )
}

export default App
