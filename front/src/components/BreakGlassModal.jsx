import { useState, useEffect } from 'react'

/**
 * Break-Glass Modal Component
 * 
 * Handles re-authentication for elevated terminal access.
 * Requires password verification and optional TOTP code.
 * Returns a short-lived breakglass_token on success.
 */
export default function BreakGlassModal({
    isOpen,
    onClose,
    onSuccess,
    hasTotp = false
}) {
    const [password, setPassword] = useState('')
    const [totpCode, setTotpCode] = useState('')
    const [loading, setLoading] = useState(false)
    const [error, setError] = useState(null)
    const [checkingStatus, setCheckingStatus] = useState(true)
    const [existingSession, setExistingSession] = useState(null)

    // Check for existing break-glass session on mount
    useEffect(() => {
        if (isOpen) {
            checkExistingSession()
        }
    }, [isOpen])

    const checkExistingSession = async () => {
        setCheckingStatus(true)
        try {
            const token = localStorage.getItem('access_token')
            const response = await fetch('/api/terminal/breakglass/status', {
                headers: {
                    'Authorization': `Bearer ${token}`
                }
            })

            if (response.ok) {
                const data = await response.json()
                if (data.active) {
                    setExistingSession(data)
                }
            }
        } catch (e) {
            console.error('Failed to check break-glass status:', e)
        } finally {
            setCheckingStatus(false)
        }
    }

    const handleSubmit = async (e) => {
        e.preventDefault()
        setLoading(true)
        setError(null)

        try {
            const token = localStorage.getItem('access_token')

            const response = await fetch('/api/terminal/breakglass/start', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${token}`
                },
                body: JSON.stringify({
                    password,
                    totp_code: totpCode || null
                })
            })

            if (!response.ok) {
                const data = await response.json()
                throw new Error(data.detail || 'Authentication failed')
            }

            const data = await response.json()

            // Clear form
            setPassword('')
            setTotpCode('')

            // Call success callback with the break-glass token
            // IMPORTANT: This token should be stored in memory only, not localStorage
            onSuccess(data.breakglass_token, data.expires_at, data.ttl_seconds)

        } catch (err) {
            setError(err.message)
        } finally {
            setLoading(false)
        }
    }

    const handleCloseSession = async () => {
        setLoading(true)
        try {
            const token = localStorage.getItem('access_token')
            await fetch('/api/terminal/breakglass/stop', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${token}`
                },
                body: JSON.stringify({ reason: 'user_cancelled' })
            })
            setExistingSession(null)
        } catch (e) {
            console.error('Failed to close session:', e)
        } finally {
            setLoading(false)
        }
    }

    if (!isOpen) return null

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
            {/* Backdrop */}
            <div
                className="absolute inset-0 bg-black/70 backdrop-blur-sm"
                onClick={onClose}
            />

            {/* Modal */}
            <div className="relative bg-gray-900 border border-red-500/30 rounded-xl p-6 w-full max-w-md shadow-2xl shadow-red-500/10">
                {/* Header */}
                <div className="flex items-center gap-3 mb-6">
                    <div className="p-2 bg-red-500/20 rounded-lg">
                        <svg className="w-6 h-6 text-red-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                        </svg>
                    </div>
                    <div>
                        <h3 className="text-lg font-bold text-gray-100">Break-Glass Access</h3>
                        <p className="text-sm text-gray-400">Emergency full shell access</p>
                    </div>
                </div>

                {/* Warning Banner */}
                <div className="mb-6 p-3 bg-red-500/10 border border-red-500/30 rounded-lg">
                    <p className="text-sm text-red-300">
                        ⚠️ Full shell access is logged and time-limited. Only use for emergency maintenance.
                    </p>
                </div>

                {checkingStatus ? (
                    <div className="flex items-center justify-center py-8">
                        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-400"></div>
                    </div>
                ) : existingSession ? (
                    /* Existing Session */
                    <div className="text-center py-4">
                        <p className="text-gray-300 mb-2">You have an active break-glass session</p>
                        <p className="text-lg font-mono text-yellow-400 mb-4">
                            {Math.floor(existingSession.remaining_seconds / 60)}:{String(existingSession.remaining_seconds % 60).padStart(2, '0')} remaining
                        </p>
                        <div className="flex gap-3 justify-center">
                            <button
                                onClick={() => onSuccess(null, existingSession.expires_at, existingSession.remaining_seconds)}
                                className="btn btn-primary"
                            >
                                Continue Session
                            </button>
                            <button
                                onClick={handleCloseSession}
                                disabled={loading}
                                className="btn btn-danger"
                            >
                                {loading ? 'Closing...' : 'End Session'}
                            </button>
                        </div>
                    </div>
                ) : (
                    /* Authentication Form */
                    <form onSubmit={handleSubmit}>
                        {error && (
                            <div className="mb-4 p-3 bg-red-500/20 border border-red-500/30 rounded-lg text-red-400 text-sm">
                                {error}
                            </div>
                        )}

                        <div className="space-y-4">
                            {/* Password Field */}
                            <div>
                                <label className="block text-sm font-medium text-gray-300 mb-2">
                                    Password
                                </label>
                                <input
                                    type="password"
                                    value={password}
                                    onChange={(e) => setPassword(e.target.value)}
                                    className="w-full px-4 py-3 bg-gray-800 border border-gray-700 rounded-lg text-gray-100 focus:outline-none focus:ring-2 focus:ring-red-500/50 focus:border-red-500"
                                    placeholder="Enter your password"
                                    required
                                    autoFocus
                                />
                            </div>

                            {/* TOTP Field (conditional) */}
                            {hasTotp && (
                                <div>
                                    <label className="block text-sm font-medium text-gray-300 mb-2">
                                        Authenticator Code
                                    </label>
                                    <input
                                        type="text"
                                        value={totpCode}
                                        onChange={(e) => setTotpCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
                                        className="w-full px-4 py-3 bg-gray-800 border border-gray-700 rounded-lg text-gray-100 focus:outline-none focus:ring-2 focus:ring-red-500/50 focus:border-red-500 font-mono text-center text-lg tracking-widest"
                                        placeholder="000000"
                                        maxLength={6}
                                        required
                                    />
                                </div>
                            )}
                        </div>

                        {/* Actions */}
                        <div className="flex gap-3 mt-6">
                            <button
                                type="button"
                                onClick={onClose}
                                className="flex-1 px-4 py-3 bg-gray-700 hover:bg-gray-600 text-gray-200 rounded-lg transition-colors"
                            >
                                Cancel
                            </button>
                            <button
                                type="submit"
                                disabled={loading || !password || (hasTotp && totpCode.length !== 6)}
                                className="flex-1 px-4 py-3 bg-red-600 hover:bg-red-500 disabled:opacity-50 disabled:cursor-not-allowed text-white font-medium rounded-lg transition-colors"
                            >
                                {loading ? (
                                    <span className="flex items-center justify-center gap-2">
                                        <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white"></div>
                                        Authenticating...
                                    </span>
                                ) : (
                                    'Authenticate'
                                )}
                            </button>
                        </div>
                    </form>
                )}

                {/* Close button */}
                <button
                    onClick={onClose}
                    className="absolute top-4 right-4 text-gray-500 hover:text-gray-300"
                >
                    <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                    </svg>
                </button>
            </div>
        </div>
    )
}
