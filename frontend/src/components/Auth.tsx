import { useState, useEffect, createContext, useContext, type ReactNode } from 'react'

// Wrap fetch to auto-include auth token
const originalFetch = window.fetch.bind(window)
window.fetch = async (input: RequestInfo | URL, init?: RequestInit) => {
  const token = localStorage.getItem('auth_token')
  if (token) {
    const headers = new Headers(init?.headers)
    headers.set('Authorization', `Bearer ${token}`)
    init = { ...init, headers }
  }
  return originalFetch(input, init)
}

interface AuthContextValue {
  token: string | null
  login: (password: string) => Promise<boolean>
  logout: () => void
  ready: boolean
}

const AuthContext = createContext<AuthContextValue>({
  token: null,
  login: async () => false,
  logout: () => {},
  ready: false,
})

export const useAuth = () => useContext(AuthContext)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState<string | null>(null)
  const [ready, setReady] = useState(false)

  useEffect(() => {
    const saved = localStorage.getItem('auth_token')
    if (saved) {
      // Verify token is still valid
      fetch('/api/auth/check', {
        headers: { Authorization: `Bearer ${saved}` },
      }).then(r => {
        if (r.ok) setToken(saved)
        else localStorage.removeItem('auth_token')
      }).finally(() => setReady(true))
    } else {
      setReady(true)
    }
  }, [])

  const login = async (password: string): Promise<boolean> => {
    try {
      const res = await fetch('/api/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ password }),
      })
      if (!res.ok) return false
      const data = await res.json()
      localStorage.setItem('auth_token', data.token)
      setToken(data.token)
      return true
    } catch {
      return false
    }
  }

  const logout = () => {
    const saved = localStorage.getItem('auth_token')
    if (saved) {
      fetch('/api/auth/logout', {
        method: 'POST',
        headers: { Authorization: `Bearer ${saved}` },
      })
    }
    localStorage.removeItem('auth_token')
    setToken(null)
  }

  return (
    <AuthContext.Provider value={{ token, login, logout, ready }}>
      {children}
    </AuthContext.Provider>
  )
}
