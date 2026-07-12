import { useState } from 'react'
import { api } from '../services/api'
import { Shield, AlertTriangle, Lock, X } from 'lucide-react'

export default function BreakGlassModal({ isOpen, onClose, onSuccess }) {
    const [password, setPassword] = useState('')
    const [error, setError] = useState(null)
    const [loading, setLoading] = useState(false)

    if (!isOpen) return null

    const handleSubmit = async (e) => {
        e.preventDefault()
        setLoading(true)
        setError(null)

        try {
            const response = await api.post('/terminal/breakglass/start', {
                password
            })

            if (response.data.breakglass_token) {
                onSuccess(response.data.breakglass_token)
                onClose()
            }
        } catch (err) {
            console.error(err)
            setError(err.response?.data?.detail || 'Authentication failed')
        } finally {
            setLoading(false)
        }
    }

    return (
        <div className="fixed inset-0 bg-black/80 backdrop-blur-sm z-50 flex items-center justify-center p-4 animate-fade-in">
            <div className="bg-gray-900 border border-red-500/30 rounded-2xl w-full max-w-md shadow-2xl overflow-hidden animate-scale-in">
                {/* Header */}
                <div className="bg-red-500/10 border-b border-red-500/20 p-4 flex items-center gap-3">
                    <div className="p-2 bg-red-500/20 rounded-lg text-red-400">
                        <Shield size={24} />
                    </div>
                    <div>
                        <h3 className="text-lg font-bold text-red-50">Break Glass Access</h3>
                        <p className="text-xs text-red-300/70">Elevated privileges required</p>
                    </div>
                    <button
                        onClick={onClose}
                        className="ml-auto text-gray-400 hover:text-white transition-colors"
                    >
                        <X size={20} />
                    </button>
                </div>

                {/* Body */}
                <div className="p-6 space-y-4">
                    <div className="bg-yellow-500/10 border border-yellow-500/20 rounded-lg p-3 flex gap-3">
                        <AlertTriangle className="text-yellow-500 shrink-0" size={20} />
                        <p className="text-xs text-yellow-200/80 leading-relaxed">
                            You are about to enter <strong>Full Shell Mode</strong>.
                            This session will be audit logged and automatically closed after 10 minutes of inactivity.
                        </p>
                    </div>

                    <form onSubmit={handleSubmit} className="space-y-4">
                        <div>
                            <label className="block text-sm font-medium text-gray-400 mb-1.5">
                                Panel Login Password
                            </label>
                            <div className="relative">
                                <Lock className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500" size={16} />
                                <input
                                    type="password"
                                    value={password}
                                    onChange={(e) => setPassword(e.target.value)}
                                    className="w-full bg-gray-950 border border-gray-800 rounded-lg py-2.5 pl-10 pr-4 text-gray-100 placeholder-gray-600 focus:outline-none focus:border-red-500/50 focus:ring-1 focus:ring-red-500/50 transition-all font-mono text-sm"
                                    placeholder="Enter password..."
                                    autoFocus
                                    required
                                />
                            </div>
                        </div>

                        {error && (
                            <div className="text-xs text-red-400 bg-red-500/10 border border-red-500/20 rounded p-2">
                                {error}
                            </div>
                        )}

                        <div className="flex gap-3 pt-2">
                            <button
                                type="button"
                                onClick={onClose}
                                className="flex-1 px-4 py-2 rounded-lg border border-gray-700 text-gray-400 hover:bg-gray-800 hover:text-white transition-all text-sm font-medium"
                            >
                                Cancel
                            </button>
                            <button
                                type="submit"
                                disabled={loading}
                                className="flex-1 px-4 py-2 rounded-lg bg-red-600 hover:bg-red-500 text-white shadow-lg shadow-red-900/20 transition-all text-sm font-bold flex items-center justify-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
                            >
                                {loading ? 'Verifying...' : 'Authenticate'}
                            </button>
                        </div>
                    </form>
                </div>
            </div>
        </div>
    )
}
