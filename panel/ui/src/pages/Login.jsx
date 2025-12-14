import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth'

export default function Login() {
    const [username, setUsername] = useState('')
    const [password, setPassword] = useState('')
    const [totpCode, setTotpCode] = useState('')
    const [needsTotp, setNeedsTotp] = useState(false)
    const [loading, setLoading] = useState(false)
    const [error, setError] = useState('')

    const { login } = useAuth()
    const navigate = useNavigate()

    const handleSubmit = async (e) => {
        e.preventDefault()
        setError('')
        setLoading(true)

        try {
            await login(username, password, needsTotp ? totpCode : null)
            navigate('/')
        } catch (err) {
            if (err.message.includes('TOTP')) {
                setNeedsTotp(true)
            } else {
                setError(err.message)
            }
        } finally {
            setLoading(false)
        }
    }

    return (
        <div className="min-h-screen flex items-center justify-center bg-dark-300 p-4 relative overflow-hidden">
            {/* Aurora background effect */}
            <div className="absolute inset-0 bg-aurora pointer-events-none"></div>
            <div className="absolute top-1/4 left-1/2 -translate-x-1/2 w-[600px] h-[400px] bg-primary-500/20 rounded-full blur-[120px] pointer-events-none"></div>

            <div className="w-full max-w-md relative z-10">
                {/* Logo */}
                <div className="text-center mb-8 animate-fade-in">
                    <div className="inline-flex items-center justify-center w-20 h-20 rounded-2xl bg-gradient-to-br from-primary-500 to-primary-700 shadow-neon-lg mb-4">
                        <span className="text-4xl">🥧</span>
                    </div>
                    <h1 className="text-4xl font-bold gradient-text mb-2">Pi Control</h1>
                    <p className="text-gray-500">Universal Control Panel</p>
                </div>

                {/* Login card */}
                <div className="glass-card rounded-2xl p-8 animate-slide-in border-glow">
                    <h2 className="text-2xl font-semibold text-white mb-6">Sign In</h2>

                    {error && (
                        <div className="mb-4 p-3 bg-red-500/10 border border-red-500/30 rounded-xl text-red-400 text-sm">
                            {error}
                        </div>
                    )}

                    <form onSubmit={handleSubmit} className="space-y-5">
                        <div>
                            <label className="block text-sm font-medium text-gray-400 mb-2">
                                Username
                            </label>
                            <input
                                type="text"
                                value={username}
                                onChange={(e) => setUsername(e.target.value)}
                                className="input"
                                placeholder="Enter username"
                                required
                                autoFocus
                            />
                        </div>

                        <div>
                            <label className="block text-sm font-medium text-gray-400 mb-2">
                                Password
                            </label>
                            <input
                                type="password"
                                value={password}
                                onChange={(e) => setPassword(e.target.value)}
                                className="input"
                                placeholder="Enter password"
                                required
                            />
                        </div>

                        {needsTotp && (
                            <div className="animate-fade-in">
                                <label className="block text-sm font-medium text-gray-400 mb-2">
                                    Two-Factor Code
                                </label>
                                <input
                                    type="text"
                                    value={totpCode}
                                    onChange={(e) => setTotpCode(e.target.value)}
                                    className="input text-center tracking-[0.5em] font-mono"
                                    placeholder="000000"
                                    maxLength={6}
                                    pattern="[0-9]{6}"
                                    autoFocus
                                />
                            </div>
                        )}

                        <button
                            type="submit"
                            disabled={loading}
                            className="w-full btn btn-primary py-3.5 text-lg font-semibold"
                        >
                            {loading ? (
                                <span className="flex items-center justify-center gap-2">
                                    <span className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin"></span>
                                    Signing in...
                                </span>
                            ) : (
                                'Sign In'
                            )}
                        </button>
                    </form>

                    <p className="mt-6 text-center text-sm text-gray-500">
                        🔒 Secure access via Tailscale
                    </p>
                </div>

                {/* Version info */}
                <p className="text-center text-xs text-gray-600 mt-6">
                    Pi Control Panel v2.0 • Cyberpunk Edition
                </p>
            </div>
        </div>
    )
}
