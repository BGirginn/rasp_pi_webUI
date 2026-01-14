import { useState, useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth'
import { initLuxuryNetwork } from '../utils/network'
import Loader from '../components/common/Loader'
import './login.css'
import { Eye, EyeOff } from 'lucide-react'

export default function Login() {
    const [username, setUsername] = useState('')
    const [password, setPassword] = useState('')
    const [showPassword, setShowPassword] = useState(false)
    const [totpCode, setTotpCode] = useState('')
    const [needsTotp, setNeedsTotp] = useState(false)
    const [loading, setLoading] = useState(false)
    const [error, setError] = useState('')

    const canvasRef = useRef(null)
    const networkRef = useRef(null)

    const { login } = useAuth()
    const navigate = useNavigate()

    // Initialize animated background
    useEffect(() => {
        if (canvasRef.current && !networkRef.current) {
            networkRef.current = initLuxuryNetwork({
                canvas: canvasRef.current,
                seed: 1337,
                density: 0.000055,
                motion: { pointer: true }
            })
            networkRef.current.start()
        }

        const handleResize = () => {
            if (networkRef.current) {
                networkRef.current.resize()
            }
        }

        window.addEventListener('resize', handleResize)

        return () => {
            window.removeEventListener('resize', handleResize)
            if (networkRef.current) {
                networkRef.current.stop()
            }
        }
    }, [])

    const handleSubmit = async (e) => {
        e.preventDefault()
        setError('')
        // Local loading state only used for button, global loading handled by useAuth
        setLoading(true)

        try {
            await login(username, password, needsTotp ? totpCode : null)
            navigate('/')
        } catch (err) {
            if (err.message?.includes('TOTP')) {
                setNeedsTotp(true)
            } else {
                setError(err.message)
            }
        } finally {
            setLoading(false)
        }
    }

    return (
        <div className="login-page min-h-screen overflow-hidden" style={{ background: 'var(--bg-0)' }}>
            {loading && <Loader text="Signing In..." />}
            {/* Animated gold network background */}
            <canvas ref={canvasRef} className="login-canvas" aria-hidden="true" />

            {/* Subtle grid overlay */}
            <div className="login-grid-overlay" aria-hidden="true" />

            {/* Purple aura + vignette */}
            <div className="login-aura" aria-hidden="true" />
            <div className="login-vignette" aria-hidden="true" />

            <main className="login-shell">
                <section className="login-card" role="dialog" aria-label="Sign in">
                    <div className="login-brand">
                        <div className="login-logo" aria-hidden="true">π</div>
                        <div className="login-brand-text">
                            <h1>Pi Control</h1>
                            <p>UNIVERSAL CONTROL PANEL</p>
                        </div>
                    </div>

                    <h2>Sign in to continue</h2>

                    {error && (
                        <div className="login-error">
                            {error}
                        </div>
                    )}

                    <form className="login-form" onSubmit={handleSubmit} autoComplete="on">
                        <label className="login-field">
                            <span>Username</span>
                            <input
                                type="text"
                                name="username"
                                placeholder="Enter username"
                                value={username}
                                onChange={(e) => setUsername(e.target.value)}
                                required
                                autoFocus
                            />
                        </label>

                        <label className="login-field">
                            <span>Password</span>
                            <input
                                type="password"
                                name="password"
                                placeholder="Enter password"
                                value={password}
                                onChange={(e) => setPassword(e.target.value)}
                                required
                            />
                        </label>

                        {needsTotp && (
                            <label className="login-field">
                                <span>2FA Code</span>
                                <input
                                    type="text"
                                    name="totp"
                                    placeholder="000000"
                                    value={totpCode}
                                    onChange={(e) => setTotpCode(e.target.value)}
                                    maxLength={6}
                                    pattern="[0-9]{6}"
                                    style={{ textAlign: 'center', letterSpacing: '0.5em', fontFamily: 'monospace', fontSize: '18px' }}
                                    autoFocus
                                />
                            </label>
                        )}

                        <button className="login-btn" type="submit" disabled={loading}>
                            {loading ? (
                                <>
                                    <span className="login-spinner" />
                                    Signing in...
                                </>
                            ) : (
                                'Sign In'
                            )}
                        </button>

                        <div className="login-hint">
                            <span aria-hidden="true">🔒</span>
                            Secure access via Tailscale VPN
                        </div>
                    </form>

                    <footer className="login-footer">PI CONTROL v2.0 • NEON EDITION</footer>
                </section>
            </main>
        </div>
    )
}
