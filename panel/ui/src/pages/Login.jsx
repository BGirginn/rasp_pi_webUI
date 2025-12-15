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
        <div className="min-h-screen flex items-center justify-center bg-black p-4 relative overflow-hidden">
            {/* Deep aurora background */}
            <div className="absolute inset-0 pointer-events-none">
                <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[800px] h-[600px] bg-purple-600/10 rounded-full blur-[150px]"></div>
                <div className="absolute bottom-0 right-0 w-[400px] h-[400px] bg-pink-600/5 rounded-full blur-[100px]"></div>
                <div className="absolute top-1/2 left-0 w-[300px] h-[300px] bg-blue-600/5 rounded-full blur-[80px]"></div>
            </div>

            {/* Grid pattern overlay */}
            <div className="absolute inset-0 opacity-[0.02]" style={{
                backgroundImage: `url("data:image/svg+xml,%3Csvg width='60' height='60' viewBox='0 0 60 60' xmlns='http://www.w3.org/2000/svg'%3E%3Cg fill='none' fill-rule='evenodd'%3E%3Cg fill='%23ffffff' fill-opacity='1'%3E%3Cpath d='M36 34v-4h-2v4h-4v2h4v4h2v-4h4v-2h-4zm0-30V0h-2v4h-4v2h4v4h2V6h4V4h-4zM6 34v-4H4v4H0v2h4v4h2v-4h4v-2H6zM6 4V0H4v4H0v2h4v4h2V6h4V4H6z'/%3E%3C/g%3E%3C/g%3E%3C/svg%3E")`
            }}></div>

            <div className="w-full max-w-md relative z-10">
                {/* Logo */}
                <div className="text-center mb-10 animate-fade-in">
                    <div className="inline-flex items-center justify-center w-20 h-20 rounded-2xl bg-gradient-to-br from-purple-600 to-pink-600 shadow-[0_0_60px_rgba(168,85,247,0.4)] mb-6">
                        <span className="text-4xl text-white font-light">π</span>
                    </div>
                    <h1 className="text-4xl font-bold gradient-text mb-2">Pi Control</h1>
                    <p className="text-zinc-600 text-sm tracking-wider uppercase">Universal Control Panel</p>
                </div>

                {/* Login card */}
                <div className="glass-card p-8 animate-slide-in">
                    <h2 className="text-xl font-semibold text-white mb-6">Sign in to continue</h2>

                    {error && (
                        <div className="mb-5 p-4 bg-red-500/10 border border-red-500/20 rounded-xl text-red-400 text-sm">
                            {error}
                        </div>
                    )}

                    <form onSubmit={handleSubmit} className="space-y-5">
                        <div>
                            <label className="block text-xs font-medium text-zinc-500 uppercase tracking-wider mb-2">
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
                            <label className="block text-xs font-medium text-zinc-500 uppercase tracking-wider mb-2">
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
                                <label className="block text-xs font-medium text-zinc-500 uppercase tracking-wider mb-2">
                                    2FA Code
                                </label>
                                <input
                                    type="text"
                                    value={totpCode}
                                    onChange={(e) => setTotpCode(e.target.value)}
                                    className="input text-center tracking-[0.5em] font-mono text-lg"
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
                            className="w-full btn btn-primary py-4 text-base mt-2"
                        >
                            {loading ? (
                                <span className="flex items-center justify-center gap-3">
                                    <span className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin"></span>
                                    Signing in...
                                </span>
                            ) : (
                                'Sign In'
                            )}
                        </button>
                    </form>

                    <div className="mt-8 pt-6 border-t border-white/[0.03] text-center">
                        <p className="text-xs text-zinc-600">
                            🔒 Secure access via Tailscale VPN
                        </p>
                    </div>
                </div>

                {/* Version */}
                <p className="text-center text-[10px] text-zinc-700 mt-8 tracking-wider">
                    PI CONTROL v2.0 • NEON EDITION
                </p>
            </div>
        </div>
    )
}
