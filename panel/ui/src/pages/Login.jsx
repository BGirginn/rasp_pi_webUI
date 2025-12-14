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
        <div className="min-h-screen flex items-center justify-center bg-gray-900 p-4">
            <div className="w-full max-w-md">
                {/* Logo */}
                <div className="text-center mb-8">
                    <h1 className="text-4xl font-bold gradient-text mb-2">Pi Control</h1>
                    <p className="text-gray-500">Universal Control Panel</p>
                </div>

                {/* Login card */}
                <div className="glass-card rounded-2xl p-8 animate-slide-in">
                    <h2 className="text-2xl font-semibold text-gray-100 mb-6">Sign In</h2>

                    {error && (
                        <div className="mb-4 p-3 bg-red-500/20 border border-red-500/30 rounded-lg text-red-400 text-sm">
                            {error}
                        </div>
                    )}

                    <form onSubmit={handleSubmit} className="space-y-4">
                        <div>
                            <label className="block text-sm font-medium text-gray-400 mb-1">
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
                            <label className="block text-sm font-medium text-gray-400 mb-1">
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
                                <label className="block text-sm font-medium text-gray-400 mb-1">
                                    Two-Factor Code
                                </label>
                                <input
                                    type="text"
                                    value={totpCode}
                                    onChange={(e) => setTotpCode(e.target.value)}
                                    className="input"
                                    placeholder="Enter 6-digit code"
                                    maxLength={6}
                                    pattern="[0-9]{6}"
                                    autoFocus
                                />
                            </div>
                        )}

                        <button
                            type="submit"
                            disabled={loading}
                            className="w-full btn btn-primary py-3 text-lg"
                        >
                            {loading ? (
                                <span className="flex items-center gap-2">
                                    <span className="animate-spin">⏳</span>
                                    Signing in...
                                </span>
                            ) : (
                                'Sign In'
                            )}
                        </button>
                    </form>

                    <p className="mt-6 text-center text-sm text-gray-500">
                        Secure access via Tailscale
                    </p>
                </div>
            </div>
        </div>
    )
}
