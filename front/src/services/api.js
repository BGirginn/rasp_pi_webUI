/**
 * API Service
 * 
 * Axios-like fetch wrapper for API calls with auth token handling.
 */

const BASE_URL = '/api'

class ApiService {
    constructor() {
        this.baseUrl = BASE_URL
    }

    async request(method, path, data = null, options = {}) {
        const url = `${this.baseUrl}${path}`
        const token = localStorage.getItem('access_token')

        const headers = {
            'Content-Type': 'application/json',
            ...options.headers,
        }

        if (token) {
            headers['Authorization'] = `Bearer ${token}`
        }

        const config = {
            method,
            headers,
            credentials: 'include', // For refresh token cookie
        }

        if (data && method !== 'GET') {
            config.body = JSON.stringify(data)
        }

        const response = await fetch(url, config)

        // Handle 401 - try token refresh
        if (response.status === 401 && path !== '/auth/refresh' && path !== '/auth/login') {
            try {
                await this.refreshToken()
                // Retry original request
                const newToken = localStorage.getItem('access_token')
                headers['Authorization'] = `Bearer ${newToken}`
                config.headers = headers
                const retryResponse = await fetch(url, config)
                return this.handleResponse(retryResponse)
            } catch (err) {
                // Refresh failed, redirect to login
                localStorage.removeItem('access_token')
                if (!window.location.pathname.includes('/login')) {
                    window.location.href = '/login'
                }
                throw err
            }
        }

        return this.handleResponse(response)
    }

    async handleResponse(response) {
        const data = await response.json().catch(() => ({}))

        if (!response.ok) {
            const error = new Error(data.detail || response.statusText)
            error.response = { status: response.status, data }
            throw error
        }

        return { data, status: response.status }
    }

    async refreshToken() {
        const response = await fetch(`${this.baseUrl}/auth/refresh`, {
            method: 'POST',
            credentials: 'include',
        })

        if (!response.ok) {
            throw new Error('Token refresh failed')
        }

        const data = await response.json()
        localStorage.setItem('access_token', data.access_token)
        return data
    }

    async logout() {
        try {
            await this.post('/auth/logout')
        } catch (err) {
            console.warn('Logout API call failed', err)
        } finally {
            localStorage.removeItem('access_token')
            window.location.href = '/login'
        }
    }

    get(path, options = {}) {
        return this.request('GET', path, null, options)
    }

    post(path, data = {}, options = {}) {
        return this.request('POST', path, data, options)
    }

    put(path, data = {}, options = {}) {
        return this.request('PUT', path, data, options)
    }

    patch(path, data = {}, options = {}) {
        return this.request('PATCH', path, data, options)
    }

    delete(path, options = {}) {
        return this.request('DELETE', path, null, options)
    }
}

export const api = new ApiService()
