import { useEffect, useState } from 'react'
import { clearSession, saveSession } from '../api/client'
import { AuthContext } from './context'

function readStoredUser() {
  try {
    return JSON.parse(localStorage.getItem('kahvecell_user') || 'null')
  } catch (error) {
    if (!(error instanceof SyntaxError)) throw error
    localStorage.removeItem('kahvecell_user')
    return null
  }
}

export function AuthProvider({ children }) {
  const [accessToken, setAccessToken] = useState(() =>
    localStorage.getItem('kahvecell_access_token'),
  )
  const [user, setUser] = useState(readStoredUser)

  useEffect(() => {
    function syncSession() {
      setAccessToken(localStorage.getItem('kahvecell_access_token'))
      setUser(readStoredUser())
    }

    window.addEventListener('kahvecell:auth-change', syncSession)
    return () => window.removeEventListener('kahvecell:auth-change', syncSession)
  }, [])

  function signIn(tokens) {
    saveSession(tokens)
    setAccessToken(tokens.access_token)
    setUser(tokens.user)
  }

  function signOut() {
    clearSession()
    setAccessToken(null)
    setUser(null)
  }

  return (
    <AuthContext.Provider
      value={{
        user,
        loading: false,
        isAuthenticated: Boolean(accessToken && user),
        signIn,
        signOut,
      }}
    >
      {children}
    </AuthContext.Provider>
  )
}
