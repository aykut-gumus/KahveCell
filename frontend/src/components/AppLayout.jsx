import { Link, NavLink, Outlet } from 'react-router-dom'
import { useAuth } from '../auth/useAuth'

export default function AppLayout() {
  const { user, signOut } = useAuth()

  return (
    <div className="app-shell">
      <header className="topbar">
        <Link className="brand" to="/">
          KahveCell
        </Link>
        <nav aria-label="Ana menü">
          <NavLink to="/">Dükkânlar</NavLink>
          <NavLink to="/subscription">Abonelik</NavLink>
          <NavLink to="/history">Sipariş geçmişi</NavLink>
        </nav>
        <div className="account">
          <span>{user?.phone_number}</span>
          <button className="button button-quiet" onClick={signOut} type="button">
            Çıkış
          </button>
        </div>
      </header>
      <main className="page-container">
        <Outlet />
      </main>
    </div>
  )
}
