import { useState, useEffect } from 'react'
import { api } from '../services/api'
import { useAuth } from '../hooks/useAuth'

// Profile section
function ProfileSection({ user, onUpdate }) {
    const [editing, setEditing] = useState(false)
    const [email, setEmail] = useState(user?.email || '')
    const [saving, setSaving] = useState(false)

    const handleSave = async () => {
        setSaving(true)
        try {
            await api.put('/auth/me', { email })
            onUpdate()
            setEditing(false)
        } catch (err) {
            alert(`Failed to update: ${err.message}`)
        } finally {
            setSaving(false)
        }
    }

    return (
        <div className="glass-card rounded-xl p-5">
            <h3 className="text-lg font-semibold text-gray-100 mb-4">👤 Profile</h3>

            <div className="space-y-4">
                <div>
                    <label className="text-sm text-gray-500">Username</label>
                    <p className="text-gray-100 font-medium">{user?.username}</p>
                </div>

                <div>
                    <label className="text-sm text-gray-500">Role</label>
                    <p className="text-gray-100">
                        <span className={`px-2 py-1 rounded-full text-xs font-medium ${user?.role === 'admin' ? 'bg-purple-500/20 text-purple-400' :
                                user?.role === 'operator' ? 'bg-blue-500/20 text-blue-400' :
                                    'bg-gray-500/20 text-gray-400'
                            }`}>
                            {user?.role}
                        </span>
                    </p>
                </div>

                <div>
                    <label className="text-sm text-gray-500">Email</label>
                    {editing ? (
                        <div className="flex gap-2 mt-1">
                            <input
                                type="email"
                                value={email}
                                onChange={(e) => setEmail(e.target.value)}
                                className="input flex-1"
                            />
                            <button onClick={handleSave} disabled={saving} className="btn btn-primary">
                                {saving ? '...' : 'Save'}
                            </button>
                            <button onClick={() => setEditing(false)} className="btn btn-ghost">
                                Cancel
                            </button>
                        </div>
                    ) : (
                        <div className="flex items-center justify-between">
                            <p className="text-gray-100">{user?.email || 'Not set'}</p>
                            <button onClick={() => setEditing(true)} className="btn btn-ghost text-sm">
                                Edit
                            </button>
                        </div>
                    )}
                </div>
            </div>
        </div>
    )
}

// TOTP section
function TOTPSection({ user, onUpdate }) {
    const [step, setStep] = useState('idle') // idle, setup, verify
    const [qrCode, setQrCode] = useState(null)
    const [secret, setSecret] = useState(null)
    const [code, setCode] = useState('')
    const [error, setError] = useState(null)

    const startSetup = async () => {
        try {
            const response = await api.post('/auth/totp/setup')
            setQrCode(response.data.qr_code)
            setSecret(response.data.secret)
            setStep('setup')
        } catch (err) {
            setError(`Failed to start setup: ${err.message}`)
        }
    }

    const verifyCode = async () => {
        try {
            await api.post('/auth/totp/verify', { code })
            setStep('idle')
            onUpdate()
        } catch (err) {
            setError('Invalid code. Please try again.')
        }
    }

    const disableTotp = async () => {
        if (!confirm('Disable two-factor authentication?')) return
        try {
            await api.post('/auth/totp/disable')
            onUpdate()
        } catch (err) {
            setError(`Failed to disable: ${err.message}`)
        }
    }

    return (
        <div className="glass-card rounded-xl p-5">
            <h3 className="text-lg font-semibold text-gray-100 mb-4">🔐 Two-Factor Authentication</h3>

            {user?.has_totp ? (
                <div>
                    <div className="flex items-center gap-2 mb-4">
                        <span className="w-3 h-3 bg-green-400 rounded-full"></span>
                        <span className="text-green-400 font-medium">Enabled</span>
                    </div>
                    <p className="text-sm text-gray-500 mb-4">
                        Your account is protected with TOTP authentication.
                    </p>
                    <button onClick={disableTotp} className="btn btn-danger text-sm">
                        Disable 2FA
                    </button>
                </div>
            ) : step === 'idle' ? (
                <div>
                    <p className="text-sm text-gray-500 mb-4">
                        Add an extra layer of security to your account by enabling two-factor authentication.
                    </p>
                    <button onClick={startSetup} className="btn btn-primary">
                        Enable 2FA
                    </button>
                </div>
            ) : step === 'setup' ? (
                <div className="space-y-4">
                    <p className="text-sm text-gray-400">
                        Scan this QR code with your authenticator app (Google Authenticator, Authy, etc.)
                    </p>

                    {qrCode && (
                        <div className="p-4 bg-white rounded-lg inline-block">
                            <img src={qrCode} alt="QR Code" className="w-48 h-48" />
                        </div>
                    )}

                    <div className="p-3 bg-gray-800/50 rounded-lg">
                        <p className="text-xs text-gray-500 mb-1">Or enter this secret manually:</p>
                        <code className="text-sm text-gray-100 font-mono break-all">{secret}</code>
                    </div>

                    <div>
                        <label className="block text-sm font-medium text-gray-400 mb-1">
                            Enter the 6-digit code from your app
                        </label>
                        <div className="flex gap-2">
                            <input
                                type="text"
                                value={code}
                                onChange={(e) => setCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
                                className="input w-32 text-center font-mono text-lg tracking-widest"
                                placeholder="000000"
                                maxLength={6}
                            />
                            <button
                                onClick={verifyCode}
                                disabled={code.length !== 6}
                                className="btn btn-primary"
                            >
                                Verify
                            </button>
                            <button onClick={() => setStep('idle')} className="btn btn-ghost">
                                Cancel
                            </button>
                        </div>
                    </div>

                    {error && (
                        <div className="p-2 bg-red-500/20 border border-red-500/30 rounded text-red-400 text-sm">
                            {error}
                        </div>
                    )}
                </div>
            ) : null}
        </div>
    )
}

// Password section
function PasswordSection() {
    const [form, setForm] = useState({
        current_password: '',
        new_password: '',
        confirm_password: '',
    })
    const [saving, setSaving] = useState(false)
    const [message, setMessage] = useState(null)

    const handleSubmit = async (e) => {
        e.preventDefault()

        if (form.new_password !== form.confirm_password) {
            setMessage({ type: 'error', text: 'Passwords do not match' })
            return
        }

        if (form.new_password.length < 8) {
            setMessage({ type: 'error', text: 'Password must be at least 8 characters' })
            return
        }

        setSaving(true)
        try {
            await api.post('/auth/password/change', {
                current_password: form.current_password,
                new_password: form.new_password,
            })
            setMessage({ type: 'success', text: 'Password changed successfully' })
            setForm({ current_password: '', new_password: '', confirm_password: '' })
        } catch (err) {
            setMessage({ type: 'error', text: err.message })
        } finally {
            setSaving(false)
        }
    }

    return (
        <div className="glass-card rounded-xl p-5">
            <h3 className="text-lg font-semibold text-gray-100 mb-4">🔑 Change Password</h3>

            <form onSubmit={handleSubmit} className="space-y-4">
                <div>
                    <label className="block text-sm font-medium text-gray-400 mb-1">
                        Current Password
                    </label>
                    <input
                        type="password"
                        value={form.current_password}
                        onChange={(e) => setForm({ ...form, current_password: e.target.value })}
                        className="input"
                        required
                    />
                </div>

                <div>
                    <label className="block text-sm font-medium text-gray-400 mb-1">
                        New Password
                    </label>
                    <input
                        type="password"
                        value={form.new_password}
                        onChange={(e) => setForm({ ...form, new_password: e.target.value })}
                        className="input"
                        required
                        minLength={8}
                    />
                </div>

                <div>
                    <label className="block text-sm font-medium text-gray-400 mb-1">
                        Confirm New Password
                    </label>
                    <input
                        type="password"
                        value={form.confirm_password}
                        onChange={(e) => setForm({ ...form, confirm_password: e.target.value })}
                        className="input"
                        required
                    />
                </div>

                {message && (
                    <div className={`p-2 rounded text-sm ${message.type === 'error'
                            ? 'bg-red-500/20 border border-red-500/30 text-red-400'
                            : 'bg-green-500/20 border border-green-500/30 text-green-400'
                        }`}>
                        {message.text}
                    </div>
                )}

                <button type="submit" disabled={saving} className="btn btn-primary">
                    {saving ? 'Changing...' : 'Change Password'}
                </button>
            </form>
        </div>
    )
}

// Sessions section
function SessionsSection() {
    const [sessions, setSessions] = useState([])
    const [loading, setLoading] = useState(true)

    useEffect(() => {
        loadSessions()
    }, [])

    async function loadSessions() {
        try {
            const response = await api.get('/auth/sessions')
            setSessions(response.data)
        } catch (err) {
            console.error('Failed to load sessions:', err)
        } finally {
            setLoading(false)
        }
    }

    async function revokeSession(sessionId) {
        try {
            await api.delete(`/auth/sessions/${sessionId}`)
            await loadSessions()
        } catch (err) {
            alert(`Failed to revoke: ${err.message}`)
        }
    }

    async function revokeAll() {
        if (!confirm('Revoke all other sessions? You will stay logged in.')) return
        try {
            await api.post('/auth/sessions/revoke-all')
            await loadSessions()
        } catch (err) {
            alert(`Failed: ${err.message}`)
        }
    }

    return (
        <div className="glass-card rounded-xl p-5">
            <div className="flex items-center justify-between mb-4">
                <h3 className="text-lg font-semibold text-gray-100">📱 Active Sessions</h3>
                {sessions.length > 1 && (
                    <button onClick={revokeAll} className="btn btn-ghost text-sm text-red-400">
                        Revoke All
                    </button>
                )}
            </div>

            {loading ? (
                <p className="text-gray-500">Loading...</p>
            ) : sessions.length > 0 ? (
                <div className="space-y-3">
                    {sessions.map((session) => (
                        <div
                            key={session.id}
                            className="flex items-center justify-between p-3 bg-gray-800/50 rounded-lg"
                        >
                            <div>
                                <p className="text-sm text-gray-100">{session.device_info || 'Unknown device'}</p>
                                <p className="text-xs text-gray-500">
                                    {session.ip_address} • Created {new Date(session.created_at).toLocaleDateString()}
                                </p>
                            </div>
                            {session.current ? (
                                <span className="text-xs text-green-400">Current</span>
                            ) : (
                                <button
                                    onClick={() => revokeSession(session.id)}
                                    className="btn btn-ghost text-xs text-red-400"
                                >
                                    Revoke
                                </button>
                            )}
                        </div>
                    ))}
                </div>
            ) : (
                <p className="text-gray-500">No active sessions</p>
            )}
        </div>
    )
}

// User management section (admin only)
function UserManagement() {
    const { isAdmin } = useAuth()
    const [users, setUsers] = useState([])
    const [loading, setLoading] = useState(true)
    const [showCreate, setShowCreate] = useState(false)
    const [newUser, setNewUser] = useState({ username: '', password: '', role: 'viewer' })

    useEffect(() => {
        if (isAdmin) loadUsers()
    }, [isAdmin])

    async function loadUsers() {
        try {
            const response = await api.get('/auth/users')
            setUsers(response.data)
        } catch (err) {
            console.error('Failed to load users:', err)
        } finally {
            setLoading(false)
        }
    }

    async function createUser(e) {
        e.preventDefault()
        try {
            await api.post('/auth/users', newUser)
            setShowCreate(false)
            setNewUser({ username: '', password: '', role: 'viewer' })
            await loadUsers()
        } catch (err) {
            alert(`Failed to create user: ${err.message}`)
        }
    }

    async function deleteUser(userId) {
        if (!confirm('Delete this user?')) return
        try {
            await api.delete(`/auth/users/${userId}`)
            await loadUsers()
        } catch (err) {
            alert(`Failed to delete: ${err.message}`)
        }
    }

    if (!isAdmin) return null

    return (
        <div className="glass-card rounded-xl p-5">
            <div className="flex items-center justify-between mb-4">
                <h3 className="text-lg font-semibold text-gray-100">👥 User Management</h3>
                <button onClick={() => setShowCreate(!showCreate)} className="btn btn-primary text-sm">
                    ➕ Add User
                </button>
            </div>

            {showCreate && (
                <form onSubmit={createUser} className="mb-4 p-4 bg-gray-800/50 rounded-lg space-y-3">
                    <input
                        type="text"
                        placeholder="Username"
                        value={newUser.username}
                        onChange={(e) => setNewUser({ ...newUser, username: e.target.value })}
                        className="input"
                        required
                    />
                    <input
                        type="password"
                        placeholder="Password"
                        value={newUser.password}
                        onChange={(e) => setNewUser({ ...newUser, password: e.target.value })}
                        className="input"
                        required
                        minLength={8}
                    />
                    <select
                        value={newUser.role}
                        onChange={(e) => setNewUser({ ...newUser, role: e.target.value })}
                        className="input"
                    >
                        <option value="viewer">Viewer</option>
                        <option value="operator">Operator</option>
                        <option value="admin">Admin</option>
                    </select>
                    <button type="submit" className="btn btn-primary">Create User</button>
                </form>
            )}

            {loading ? (
                <p className="text-gray-500">Loading...</p>
            ) : (
                <div className="space-y-2">
                    {users.map((user) => (
                        <div
                            key={user.id}
                            className="flex items-center justify-between p-3 bg-gray-800/50 rounded-lg"
                        >
                            <div>
                                <p className="text-gray-100 font-medium">{user.username}</p>
                                <p className="text-xs text-gray-500">{user.role} • {user.email || 'No email'}</p>
                            </div>
                            <button
                                onClick={() => deleteUser(user.id)}
                                className="btn btn-ghost text-xs text-red-400"
                            >
                                Delete
                            </button>
                        </div>
                    ))}
                </div>
            )}
        </div>
    )
}

export default function Settings() {
    const { user, refreshUser } = useAuth()
    const [activeTab, setActiveTab] = useState('profile')

    const handleUpdate = () => {
        if (refreshUser) refreshUser()
    }

    const tabs = [
        { id: 'profile', label: '👤 Profile', component: ProfileSection },
        { id: 'security', label: '🔐 Security', component: null },
        { id: 'users', label: '👥 Users', adminOnly: true },
    ]

    return (
        <div className="space-y-6 animate-fade-in">
            {/* Header */}
            <h2 className="text-2xl font-bold text-gray-100">Settings</h2>

            {/* Tabs */}
            <div className="flex gap-2">
                {tabs.map((tab) => (
                    (!tab.adminOnly || user?.role === 'admin') && (
                        <button
                            key={tab.id}
                            onClick={() => setActiveTab(tab.id)}
                            className={`px-4 py-2 rounded-lg font-medium transition-all ${activeTab === tab.id
                                    ? 'bg-primary-600 text-white'
                                    : 'bg-gray-800 text-gray-400 hover:bg-gray-700'
                                }`}
                        >
                            {tab.label}
                        </button>
                    )
                ))}
            </div>

            {/* Content */}
            {activeTab === 'profile' && (
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                    <ProfileSection user={user} onUpdate={handleUpdate} />
                    <PasswordSection />
                </div>
            )}

            {activeTab === 'security' && (
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                    <TOTPSection user={user} onUpdate={handleUpdate} />
                    <SessionsSection />
                </div>
            )}

            {activeTab === 'users' && (
                <UserManagement />
            )}
        </div>
    )
}
