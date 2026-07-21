import { createContext, useContext, useState, useCallback } from 'react'

const AuthCtx = createContext(null)

const API = '/api'

export function AuthProvider({ children }) {
  const [user, setUser] = useState(() => {
    try {
      const s = localStorage.getItem('dcic_user')
      return s ? JSON.parse(s) : null
    } catch { return null }
  })
  const [token, setToken] = useState(() => localStorage.getItem('dcic_token') || null)

  const login = useCallback(async (email, password) => {
    const body = new URLSearchParams({ username: email, password })
    const r = await fetch(`${API}/auth/login`, { method: 'POST', body })
    if (!r.ok) {
      const err = await r.json().catch(() => ({}))
      throw new Error(err.detail || 'Credenciales incorrectas')
    }
    const data = await r.json()
    localStorage.setItem('dcic_token', data.access_token)
    localStorage.setItem('dcic_user', JSON.stringify(data.user))
    setToken(data.access_token)
    setUser(data.user)
    return data.user
  }, [])

  const logout = useCallback(() => {
    localStorage.removeItem('dcic_token')
    localStorage.removeItem('dcic_user')
    setToken(null)
    setUser(null)
  }, [])

  const authFetch = useCallback(async (url, opts = {}) => {
    const res = await fetch(url, {
      ...opts,
      headers: {
        ...(opts.headers || {}),
        Authorization: `Bearer ${token}`,
      },
    })
    if (res.status === 401) {
      localStorage.removeItem('dcic_token')
      localStorage.removeItem('dcic_user')
      setToken(null)
      setUser(null)
    }
    return res
  }, [token])

  return (
    <AuthCtx.Provider value={{ user, token, login, logout, authFetch, isAdmin: user?.rol === 'admin', isEditor: user?.rol === 'editor' || user?.rol === 'admin' }}>
      {children}
    </AuthCtx.Provider>
  )
}

export const useAuth = () => useContext(AuthCtx)
