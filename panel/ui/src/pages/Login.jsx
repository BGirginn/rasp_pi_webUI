import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ArrowRight, Eye, EyeOff, LoaderCircle, ShieldCheck, Wifi } from 'lucide-react';
import { useAuth } from '../hooks/useAuth';
import { useTheme } from '../contexts/ThemeContext';
import './login.css';

export default function Login() {
    const [username, setUsername] = useState('');
    const [password, setPassword] = useState('');
    const [showPassword, setShowPassword] = useState(false);
    const [totpCode, setTotpCode] = useState('');
    const [needsTotp, setNeedsTotp] = useState(false);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState('');
    const { login } = useAuth();
    const { theme } = useTheme();
    const navigate = useNavigate();

    async function handleSubmit(event) {
        event.preventDefault();
        setError('');
        setLoading(true);

        try {
            await login(username, password, needsTotp ? totpCode : null);
            navigate('/');
        } catch (requestError) {
            if (requestError.message?.includes('TOTP')) {
                setNeedsTotp(true);
            } else {
                setError(requestError.message);
            }
        } finally {
            setLoading(false);
        }
    }

    return (
        <div className={`login-page theme-${theme}`}>
            <div className="login-texture" aria-hidden="true" />
            <main className="login-shell">
                <section className="login-intro">
                    <div className="login-brand">
                        <div className="login-logo">π</div>
                        <div>
                            <strong>Pi Control</strong>
                            <span>Raspberry operations</span>
                        </div>
                    </div>

                    <div className="login-intro-copy">
                        <span className="login-eyebrow">Private control plane</span>
                        <h1>Your Pi, without the noise.</h1>
                        <p>Monitor services, investigate system activity and run maintenance work from one focused workspace.</p>
                    </div>

                    <div className="login-status-row">
                        <span><i /><Wifi size={15} /> Tailnet ready</span>
                        <span><ShieldCheck size={15} /> Encrypted access</span>
                    </div>
                </section>

                <section className="login-card" aria-labelledby="login-heading">
                    <div className="login-card-heading">
                        <span>Welcome back</span>
                        <h2 id="login-heading">Sign in to Pi Control</h2>
                        <p>Use your panel account to continue.</p>
                    </div>

                    {error && <div className="login-error">{error}</div>}

                    <form className="login-form" onSubmit={handleSubmit} autoComplete="on">
                        <label className="login-field">
                            <span>Username</span>
                            <input
                                type="text"
                                name="username"
                                placeholder="Enter username"
                                value={username}
                                onChange={(event) => setUsername(event.target.value)}
                                required
                                autoFocus
                            />
                        </label>

                        <label className="login-field">
                            <span>Password</span>
                            <div className="login-password-field">
                                <input
                                    type={showPassword ? 'text' : 'password'}
                                    name="password"
                                    placeholder="Enter password"
                                    value={password}
                                    onChange={(event) => setPassword(event.target.value)}
                                    required
                                />
                                <button type="button" onClick={() => setShowPassword((value) => !value)} title="Toggle password visibility">
                                    {showPassword ? <EyeOff size={17} /> : <Eye size={17} />}
                                </button>
                            </div>
                        </label>

                        {needsTotp && (
                            <label className="login-field">
                                <span>Two-factor code</span>
                                <input
                                    className="login-totp"
                                    type="text"
                                    inputMode="numeric"
                                    name="totp"
                                    placeholder="000000"
                                    value={totpCode}
                                    onChange={(event) => setTotpCode(event.target.value.replace(/\D/g, ''))}
                                    maxLength={6}
                                    pattern="[0-9]{6}"
                                    autoFocus
                                />
                            </label>
                        )}

                        <button className="login-btn" type="submit" disabled={loading}>
                            {loading ? (
                                <><LoaderCircle size={17} className="login-spinner" /> Signing in</>
                            ) : (
                                <>Continue <ArrowRight size={17} /></>
                            )}
                        </button>
                    </form>

                    <div className="login-footnote">
                        <ShieldCheck size={14} />
                        Credentials stay within your private panel.
                    </div>
                </section>
            </main>
        </div>
    );
}
