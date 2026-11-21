import { Navigate, Outlet } from 'react-router-dom'
import { useAuth } from '../auth/useAuth'

export default function ProtectedRoute() {
  const { isAuthenticated, loading } = useAuth()
  if (loading) return <p className="page-message">Oturum kontrol ediliyor…</p>
  return isAuthenticated ? <Outlet /> : <Navigate to="/login" replace />
}
