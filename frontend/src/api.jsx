import { createContext, useContext, useState } from 'react'

// ----- HTTP helper ---------------------------------------------------------

export const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000'
const STORAGE_KEY = 'placematch_auth'

export async function apiRequest(path, options) {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: { 'Content-Type': 'application/json', ...options.headers },
    ...options,
  })
  const data = await response.json().catch(() => ({}))
  if (!response.ok) throw new Error(data.detail || 'Something went wrong. Please try again.')
  return data
}

// ----- Auth context --------------------------------------------------------

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [auth, setAuth] = useState(() => {
    try { return JSON.parse(localStorage.getItem(STORAGE_KEY)) } catch { return null }
  })

  function saveAuth(loginResponse) {
    const session = {
      token: loginResponse.access_token,
      user: {
        id: loginResponse.user_id,
        email: loginResponse.email,
        fullName: loginResponse.full_name,
        role: loginResponse.role,
      },
    }
    localStorage.setItem(STORAGE_KEY, JSON.stringify(session))
    setAuth(session)
  }

  function logout() {
    localStorage.removeItem(STORAGE_KEY)
    setAuth(null)
  }

  return <AuthContext.Provider value={{ auth, saveAuth, logout }}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (!context) throw new Error('useAuth must be used inside AuthProvider')
  return context
}
