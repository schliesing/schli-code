import { Link, useLocation } from 'react-router-dom'
import { LayoutDashboard, Plus, Library } from 'lucide-react'

export default function Navbar() {
  const location = useLocation()

  const isActive = (path: string) => location.pathname === path

  return (
    <nav className="bg-white border-b border-gray-100 sticky top-0 z-40 shadow-sm">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          {/* Logo */}
          <Link to="/" className="flex items-center gap-2 group">
            <span className="text-2xl group-hover:scale-110 transition-transform">🤖</span>
            <span className="font-bold text-xl text-indigo-600">CriaBot</span>
          </Link>

          {/* Navigation links */}
          <div className="flex items-center gap-1">
            <Link
              to="/templates"
              className={`flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
                isActive('/templates')
                  ? 'bg-indigo-50 text-indigo-600'
                  : 'text-gray-600 hover:text-indigo-600 hover:bg-gray-50'
              }`}
            >
              <Library size={16} />
              <span className="hidden sm:inline">Templates</span>
            </Link>

            <Link
              to="/dashboard"
              className={`flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
                isActive('/dashboard')
                  ? 'bg-indigo-50 text-indigo-600'
                  : 'text-gray-600 hover:text-indigo-600 hover:bg-gray-50'
              }`}
            >
              <LayoutDashboard size={16} />
              <span className="hidden sm:inline">Meus Agentes</span>
            </Link>

            <Link
              to="/wizard"
              className="flex items-center gap-1.5 ml-2 bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-semibold px-4 py-2 rounded-lg transition-colors shadow-sm"
            >
              <Plus size={16} />
              <span>Criar Agente</span>
            </Link>
          </div>
        </div>
      </div>
    </nav>
  )
}
