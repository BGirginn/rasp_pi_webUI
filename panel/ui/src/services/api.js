/**
 * API Service
 * 
 * Axios-like fetch wrapper for API calls with auth token handling.
 */

const BASE_URL = '/api'

class ApiService {
    constructor() {
        this.baseUrl = BASE_URL
        this._refreshPromise = null
        this._getCache = new Map()
        this._inflightGet = new Map()
        this._cacheTtls = new Map([
            ['/alerts', 3000],
            ['/resources', 5000],
            ['/system/info', 10000],
            ['/system/processes', 10000],
            ['/telemetry/current', 1000],
        ])
    }

    async request(method, path, data = null, options = {}) {
        if (method === 'GET' && options.cache !== false && options.responseType !== 'blob' && options.responseType !== 'text') {
            const cacheKey = this._cacheKey(path, options)
            const ttlMs = this._resolveCacheTtl(path, options)
            const now = Date.now()
            const cached = this._getCache.get(cacheKey)

            if (ttlMs > 0 && cached && cached.expiresAt > now) {
                return cached.response
            }

            const inflight = this._inflightGet.get(cacheKey)
            if (inflight) {
                return inflight
            }

            const requestPromise = this._request(method, path, data, options)
                .then(response => {
                    if (ttlMs > 0) {
                        this._getCache.set(cacheKey, {
                            response,
                            expiresAt: Date.now() + ttlMs,
                        })
                    }
                    return response
                })
                .finally(() => {
                    this._inflightGet.delete(cacheKey)
                })

            this._inflightGet.set(cacheKey, requestPromise)
            return requestPromise
        }

        if (method !== 'GET') {
            this._getCache.clear()
        }

        return this._request(method, path, data, options)
    }

    async _request(method, path, data = null, options = {}) {
        const url = `${this.baseUrl}${path}`
        const token = localStorage.getItem('access_token')

        const headers = {
            'Content-Type': 'application/json',
            ...options.headers,
        }

        if (data instanceof FormData) {
            delete headers['Content-Type'];
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
            config.body = data instanceof FormData ? data : JSON.stringify(data)
        }

        const response = await fetch(url, config)

        // Handle 401 - try token refresh (singleton to prevent race condition)
        if (response.status === 401 && path !== '/auth/refresh' && path !== '/auth/login') {
            try {
                if (!this._refreshPromise) {
                    this._refreshPromise = this.refreshToken().finally(() => {
                        this._refreshPromise = null
                    })
                }
                await this._refreshPromise
                // Retry original request with new token
                const newToken = localStorage.getItem('access_token')
                headers['Authorization'] = `Bearer ${newToken}`
                config.headers = headers
                const retryResponse = await fetch(url, config)
                return this.handleResponse(retryResponse, options.responseType)
            } catch (err) {
                // Refresh failed, redirect to login
                localStorage.removeItem('access_token')
                if (!window.location.pathname.includes('/login')) {
                    window.location.href = '/login'
                }
                throw err
            }
        }

        return this.handleResponse(response, options.responseType)
    }

    _resolveCacheTtl(path, options) {
        if (typeof options.cacheTtlMs === 'number') {
            return options.cacheTtlMs
        }
        return this._cacheTtls.get(path) ?? 0
    }

    _cacheKey(path, options) {
        return `${path}:${options.responseType || 'json'}`
    }

    async handleResponse(response, responseType = 'json') {
        const errorResponse = typeof response.clone === 'function' ? response.clone() : response
        let data

        if (responseType === 'blob') {
            data = await response.blob()
        } else if (responseType === 'text') {
            data = await response.text()
        } else {
            data = await response.json().catch(() => ({}))
        }

        if (!response.ok) {
            let errorData = {}
            if (responseType === 'blob') {
                errorData = await errorResponse.json().catch(async () => {
                    const text = await errorResponse.text().catch(() => '')
                    return { detail: text || response.statusText }
                })
            } else if (typeof data === 'string') {
                errorData = { detail: data || response.statusText }
            } else {
                errorData = data
            }

            const error = new Error(errorData.detail || response.statusText)
            error.response = { status: response.status, data: errorData }
            throw error
        }

        return { data, status: response.status, headers: response.headers }
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

    /**
     * Create SSE connection for real-time updates
     * @param {string} path - SSE endpoint path
     * @param {function} onMessage - Message handler (data, eventType)
     * @param {function} onError - Error handler
     * @returns {EventSource}
     */
    createSSE(path, onMessage, onError = null) {
        const token = localStorage.getItem('access_token')
        const url = `${this.baseUrl}${path}${token ? `?token=${token}` : ''}`

        const eventSource = new EventSource(url, { withCredentials: true })

        eventSource.addEventListener('telemetry_update', (event) => {
            try {
                const data = JSON.parse(event.data)
                onMessage(data, 'telemetry_update')
            } catch (e) {
                console.error('Failed to parse SSE data:', e)
            }
        })

        eventSource.addEventListener('iot_update', (event) => {
            try {
                const data = JSON.parse(event.data)
                onMessage(data, 'iot_update')
            } catch (e) {
                console.error('Failed to parse SSE iot_update data:', e)
            }
        })

        eventSource.addEventListener('connected', (event) => {
            if (import.meta.env.DEV) {
                console.log('SSE connected:', event.data)
            }
        })

        eventSource.onerror = (error) => {
            console.warn('SSE error:', error)
            if (onError) onError(error)
        }

        return eventSource
    }
}

export const api = new ApiService()
