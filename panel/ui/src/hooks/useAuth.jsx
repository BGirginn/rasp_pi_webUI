import { createContext, useContext, useState, useEffect } from 'react'
import { api } from '../services/api'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
    const [user, setUser] = useState(null)
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState(null)

    // Check for existing session on mount
    useEffect(() => {
        checkAuth()
    }, [])

    async function checkAuth() {
        try {
            const token = localStorage.getItem('access_token')
            if (!token) {
                setLoading(false)
                return
            }

            // Try to get current user
            const response = await api.get('/auth/me')
            setUser(response.data)
        } catch {
            localStorage.removeItem('access_token')
            setUser(null)
        } finally {
            setLoading(false)
        }
    }

    async function login(username, password, totpCode = null) {
        setError(null)
        // Note: We do NOT set global loading here to keep Login component mounted

        try {
            const payload = { username, password }
            if (totpCode) {
                payload.totp_code = totpCode
            }

            // 1. Authenticate immediately
            const response = await api.post('/auth/login', payload)

            // 2. Set token immediately (so subsequent requests work)
            localStorage.setItem('access_token', response.data.access_token)

            setUser(response.data.user)

            return response.data
        } catch (err) {
            const message = err.response?.data?.detail || 'Login failed'
            setError(message)
            throw new Error(message)
        }
    }

    async function logout() {
        setLoading(true)
        try {
            await api.post('/auth/logout')
        } catch (err) {
            // Ignore logout errors
        } finally {
            localStorage.removeItem('access_token')
            setUser(null)
            setLoading(false)
        }
    }

    async function refreshToken() {
        const response = await api.post('/auth/refresh')
        localStorage.setItem('access_token', response.data.access_token)
        return response.data
    }

    const value = {
        user,
        loading,
        error,
        login,
        logout,
        refreshToken,
        isAdmin: user?.role === 'admin',
        isOperator: user?.role === 'operator' || user?.role === 'admin',
    }

    return (
        <AuthContext.Provider value={value}>
            {children}
        </AuthContext.Provider>
    )
}

export function useAuth() {
    const context = useContext(AuthContext)
    if (!context) {
        throw new Error('useAuth must be used within AuthProvider')
    }
    return context
}
