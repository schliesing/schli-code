import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import LandingPage from './pages/LandingPage'
import TemplatesGallery from './pages/TemplatesGallery'
import WizardPage from './pages/WizardPage'
import LiveTestPage from './pages/LiveTestPage'
import DashboardPage from './pages/DashboardPage'
import PaymentSuccessPage from './pages/PaymentSuccessPage'
import Navbar from './components/layout/Navbar'

function App() {
  return (
    <BrowserRouter>
      <div className="min-h-screen bg-gray-50">
        <Routes>
          {/* Pages with Navbar */}
          <Route path="/" element={<><Navbar /><LandingPage /></>} />
          <Route path="/templates" element={<><Navbar /><TemplatesGallery /></>} />
          <Route path="/dashboard" element={<><Navbar /><DashboardPage /></>} />
          {/* Pages without Navbar */}
          <Route path="/wizard" element={<WizardPage />} />
          <Route path="/wizard/:agentId" element={<WizardPage />} />
          <Route path="/test/:agentId" element={<LiveTestPage />} />
          <Route path="/payment/success" element={<PaymentSuccessPage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </div>
    </BrowserRouter>
  )
}

export default App
