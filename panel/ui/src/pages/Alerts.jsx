import { useState, useEffect, useRef } from 'react'
import { api } from '../services/api'
import { useAuth } from '../hooks/useAuth'

// Alert severity badge
function SeverityBadge({ severity }) {
    const styles = {
        critical: 'bg-red-500/20 text-red-400 border-red-500/30',
        warning: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30',
        info: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
    }

    const icons = {
        critical: '🔴',
        warning: '🟡',
        info: '🔵',
    }

    return (
        <span className={`px-2 py-1 rounded-full text-xs font-medium border ${styles[severity]}`}>
            {icons[severity]} {severity}
        </span>
    )
}

// Alert state badge
function StateBadge({ state }) {
    const styles = {
        pending: 'bg-yellow-500/20 text-yellow-400',
        firing: 'bg-red-500/20 text-red-400 animate-pulse',
        acknowledged: 'bg-blue-500/20 text-blue-400',
        resolved: 'bg-green-500/20 text-green-400',
    }

    return (
        <span className={`px-2 py-1 rounded-full text-xs font-medium ${styles[state]}`}>
            {state}
        </span>
    )
}

// Alert card component
function AlertCard({ alert, onAction }) {
    const { isOperator } = useAuth()
    const [loading, setLoading] = useState(false)

    const handleAction = async (action) => {
        setLoading(true)
        try {
            await onAction(alert.id, action)
        } finally {
            setLoading(false)
        }
    }

    return (
        <div className={`glass-card rounded-xl p-5 animate-slide-in ${alert.state === 'firing' ? 'border-l-4 border-red-500' : ''
            }`}>
            <div className="flex items-start justify-between mb-3">
                <div className="flex items-center gap-3">
                    <SeverityBadge severity={alert.severity} />
                    <StateBadge state={alert.state} />
                </div>
                <span className="text-xs text-gray-500">
                    {alert.fired_at && new Date(alert.fired_at).toLocaleString()}
                </span>
            </div>

            <h3 className="font-semibold text-gray-100 mb-1">{alert.rule_name || 'Alert'}</h3>
            <p className="text-sm text-gray-400 mb-3">{alert.message || 'No message'}</p>

            {alert.value !== null && (
                <div className="mb-3 p-2 bg-gray-800/50 rounded text-sm">
                    <span className="text-gray-500">Value: </span>
                    <span className="text-gray-100 font-mono">{alert.value}</span>
                </div>
            )}

            {/* Actions */}
            {isOperator && (alert.state === 'pending' || alert.state === 'firing') && (
                <div className="flex gap-2">
                    <button
                        onClick={() => handleAction('acknowledge')}
                        disabled={loading || alert.state === 'acknowledged'}
                        className="btn btn-secondary text-sm py-1 px-3 flex-1"
                    >
                        {loading ? '...' : '✓ Acknowledge'}
                    </button>
                    <button
                        onClick={() => handleAction('resolve')}
                        disabled={loading}
                        className="btn btn-primary text-sm py-1 px-3 flex-1"
                    >
                        {loading ? '...' : '✅ Resolve'}
                    </button>
                </div>
            )}

            {alert.acknowledged_at && (
                <p className="text-xs text-gray-500 mt-2">
                    Acknowledged: {new Date(alert.acknowledged_at).toLocaleString()}
                </p>
            )}
        </div>
    )
}

// Alert rule card
function RuleCard({ rule, onToggle, onDelete }) {
    const { isAdmin } = useAuth()

    return (
        <div className="glass-card rounded-xl p-4">
            <div className="flex items-start justify-between mb-2">
                <div>
                    <h4 className="font-medium text-gray-100">{rule.name}</h4>
                    <p className="text-xs text-gray-500">{rule.description}</p>
                </div>
                <div className="flex items-center gap-2">
                    <SeverityBadge severity={rule.severity} />
                    {isAdmin && (
                        <button
                            onClick={() => onToggle(rule.id, !rule.enabled)}
                            className={`w-12 h-6 rounded-full transition-colors ${rule.enabled ? 'bg-primary-600' : 'bg-gray-600'
                                }`}
                        >
                            <span
                                className={`block w-5 h-5 bg-white rounded-full transition-transform ${rule.enabled ? 'translate-x-6' : 'translate-x-1'
                                    }`}
                            />
                        </button>
                    )}
                </div>
            </div>

            <div className="text-sm text-gray-400 font-mono bg-gray-800/50 p-2 rounded">
                {rule.metric} {rule.condition} {rule.threshold}
            </div>

            <div className="flex justify-between items-center mt-2 text-xs text-gray-500">
                <span>Cooldown: {rule.cooldown_minutes}min</span>
                {isAdmin && (
                    <button
                        onClick={() => onDelete(rule.id)}
                        className="text-red-400 hover:text-red-300"
                    >
                        Delete
                    </button>
                )}
            </div>
        </div>
    )
}

// Create rule modal
function CreateRuleModal({ onClose, onCreate }) {
    const [form, setForm] = useState({
        name: '',
        description: '',
        metric: 'host.cpu.pct_total',
        condition: 'gt',
        threshold: 80,
        severity: 'warning',
        cooldown_minutes: 15,
    })
    const [loading, setLoading] = useState(false)
    const overlayRef = useRef(null)

    // Handle ESC key
    useEffect(() => {
        const handleKeyDown = (e) => {
            if (e.key === 'Escape') onClose()
        }
        document.addEventListener('keydown', handleKeyDown)
        document.body.style.overflow = 'hidden'
        return () => {
            document.removeEventListener('keydown', handleKeyDown)
            document.body.style.overflow = ''
        }
    }, [onClose])

    // Handle click outside
    const handleOverlayClick = (e) => {
        if (e.target === overlayRef.current) onClose()
    }

    const handleSubmit = async (e) => {
        e.preventDefault()
        setLoading(true)
        try {
            await onCreate(form)
        } finally {
            setLoading(false)
        }
    }

    return (
        <div
            ref={overlayRef}
            onClick={handleOverlayClick}
            className="fixed inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center z-50 p-4 animate-fade-in"
        >
            <div className="glass-card rounded-2xl w-full max-w-md animate-slide-in">
                {/* Header */}
                <div className="flex items-center justify-between p-5 border-b border-white/[0.03]">
                    <h2 className="text-lg font-semibold text-white">Create Alert Rule</h2>
                    <button
                        onClick={onClose}
                        className="w-8 h-8 rounded-lg bg-white/[0.03] hover:bg-white/[0.08] flex items-center justify-center text-zinc-400 hover:text-white transition-colors"
                    >
                        ✕
                    </button>
                </div>

                {/* Form */}
                <form onSubmit={handleSubmit} className="p-5 space-y-4">
                    <div>
                        <label className="block text-xs font-medium text-zinc-500 uppercase tracking-wider mb-2">Name</label>
                        <input
                            type="text"
                            value={form.name}
                            onChange={(e) => setForm({ ...form, name: e.target.value })}
                            className="input"
                            placeholder="High CPU Usage"
                            required
                            autoFocus
                        />
                    </div>

                    <div>
                        <label className="block text-xs font-medium text-zinc-500 uppercase tracking-wider mb-2">Description</label>
                        <input
                            type="text"
                            value={form.description}
                            onChange={(e) => setForm({ ...form, description: e.target.value })}
                            className="input"
                            placeholder="Alert when CPU usage is too high"
                        />
                    </div>

                    <div>
                        <label className="block text-xs font-medium text-zinc-500 uppercase tracking-wider mb-2">Metric</label>
                        <select
                            value={form.metric}
                            onChange={(e) => setForm({ ...form, metric: e.target.value })}
                            className="input"
                        >
                            <option value="host.cpu.pct_total">CPU Usage %</option>
                            <option value="host.mem.pct">Memory Usage %</option>
                            <option value="host.temp.cpu_c">CPU Temperature °C</option>
                            <option value="disk._root.used_pct">Disk Usage %</option>
                            <option value="host.load.1m">Load Average (1m)</option>
                        </select>
                    </div>

                    <div className="grid grid-cols-2 gap-4">
                        <div>
                            <label className="block text-xs font-medium text-zinc-500 uppercase tracking-wider mb-2">Condition</label>
                            <select
                                value={form.condition}
                                onChange={(e) => setForm({ ...form, condition: e.target.value })}
                                className="input"
                            >
                                <option value="gt">Greater than (&gt;)</option>
                                <option value="gte">Greater or equal (≥)</option>
                                <option value="lt">Less than (&lt;)</option>
                                <option value="lte">Less or equal (≤)</option>
                                <option value="eq">Equals (=)</option>
                            </select>
                        </div>
                        <div>
                            <label className="block text-xs font-medium text-zinc-500 uppercase tracking-wider mb-2">Threshold</label>
                            <input
                                type="number"
                                value={form.threshold}
                                onChange={(e) => setForm({ ...form, threshold: parseFloat(e.target.value) })}
                                className="input"
                                required
                            />
                        </div>
                    </div>

                    <div className="grid grid-cols-2 gap-4">
                        <div>
                            <label className="block text-xs font-medium text-zinc-500 uppercase tracking-wider mb-2">Severity</label>
                            <select
                                value={form.severity}
                                onChange={(e) => setForm({ ...form, severity: e.target.value })}
                                className="input"
                            >
                                <option value="info">Info</option>
                                <option value="warning">Warning</option>
                                <option value="critical">Critical</option>
                            </select>
                        </div>
                        <div>
                            <label className="block text-xs font-medium text-zinc-500 uppercase tracking-wider mb-2">Cooldown (min)</label>
                            <input
                                type="number"
                                value={form.cooldown_minutes}
                                onChange={(e) => setForm({ ...form, cooldown_minutes: parseInt(e.target.value) })}
                                className="input"
                                min="1"
                                max="60"
                            />
                        </div>
                    </div>

                    <div className="flex gap-3 pt-2">
                        <button type="submit" disabled={loading} className="btn btn-primary flex-1">
                            {loading ? 'Creating...' : 'Create Rule'}
                        </button>
                        <button type="button" onClick={onClose} className="btn btn-secondary">
                            Cancel
                        </button>
                    </div>
                </form>
            </div>
        </div>
    )
}

export default function Alerts() {
    const { isAdmin } = useAuth()
    const [alerts, setAlerts] = useState([])
    const [rules, setRules] = useState([])
    const [loading, setLoading] = useState(true)
    const [tab, setTab] = useState('alerts')
    const [filter, setFilter] = useState('all')
    const [showCreateRule, setShowCreateRule] = useState(false)

    useEffect(() => {
        loadData()
        const interval = setInterval(loadAlerts, 10000)
        return () => clearInterval(interval)
    }, [])

    async function loadData() {
        await Promise.all([loadAlerts(), loadRules()])
        setLoading(false)
    }

    async function loadAlerts() {
        try {
            const response = await api.get('/alerts')
            setAlerts(response.data)
        } catch (err) {
            console.error('Failed to load alerts:', err)
        }
    }

    async function loadRules() {
        try {
            const response = await api.get('/alerts/rules')
            setRules(response.data)
        } catch (err) {
            console.error('Failed to load rules:', err)
        }
    }

    async function handleAlertAction(alertId, action) {
        try {
            await api.post(`/alerts/${alertId}/${action}`)
            await loadAlerts()
        } catch (err) {
            console.error(`Failed to ${action} alert:`, err)
            alert(`Failed to ${action}: ${err.message}`)
        }
    }

    async function handleRuleToggle(ruleId, enabled) {
        try {
            await api.post(`/alerts/rules/${ruleId}/toggle?enabled=${enabled}`)
            await loadRules()
        } catch (err) {
            console.error('Failed to toggle rule:', err)
        }
    }

    async function handleRuleDelete(ruleId) {
        if (!confirm('Delete this rule?')) return
        try {
            await api.delete(`/alerts/rules/${ruleId}`)
            await loadRules()
        } catch (err) {
            console.error('Failed to delete rule:', err)
        }
    }

    async function handleCreateRule(form) {
        try {
            await api.post('/alerts/rules', form)
            setShowCreateRule(false)
            await loadRules()
        } catch (err) {
            console.error('Failed to create rule:', err)
            alert(`Failed to create rule: ${err.message}`)
        }
    }

    // Filter alerts
    const filteredAlerts = filter === 'all'
        ? alerts
        : alerts.filter((a) => a.state === filter || a.severity === filter)

    // Counts
    const counts = {
        all: alerts.length,
        firing: alerts.filter((a) => a.state === 'firing').length,
        acknowledged: alerts.filter((a) => a.state === 'acknowledged').length,
        critical: alerts.filter((a) => a.severity === 'critical').length,
    }

    if (loading) {
        return (
            <div className="flex items-center justify-center h-64">
                <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-primary-500" />
            </div>
        )
    }

    return (
        <div className="space-y-6 animate-fade-in">
            {/* Header */}
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                <h2 className="text-2xl font-bold text-gray-100">Alerts</h2>
                <div className="flex gap-3">
                    <button onClick={loadData} className="btn btn-secondary">🔄 Refresh</button>
                    {isAdmin && (
                        <button onClick={() => setShowCreateRule(true)} className="btn btn-primary">
                            ➕ Create Rule
                        </button>
                    )}
                </div>
            </div>

            {/* Summary Cards */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div className="glass-card rounded-xl p-4 text-center">
                    <p className="text-3xl font-bold text-gray-100">{counts.all}</p>
                    <p className="text-sm text-gray-500">Total Alerts</p>
                </div>
                <div className="glass-card rounded-xl p-4 text-center border-l-4 border-red-500">
                    <p className="text-3xl font-bold text-red-400">{counts.firing}</p>
                    <p className="text-sm text-gray-500">Firing</p>
                </div>
                <div className="glass-card rounded-xl p-4 text-center">
                    <p className="text-3xl font-bold text-blue-400">{counts.acknowledged}</p>
                    <p className="text-sm text-gray-500">Acknowledged</p>
                </div>
                <div className="glass-card rounded-xl p-4 text-center">
                    <p className="text-3xl font-bold text-yellow-400">{counts.critical}</p>
                    <p className="text-sm text-gray-500">Critical</p>
                </div>
            </div>

            {/* Tabs */}
            <div className="flex gap-2">
                <button
                    onClick={() => setTab('alerts')}
                    className={`px-4 py-2 rounded-lg font-medium transition-all ${tab === 'alerts' ? 'bg-primary-600 text-white' : 'bg-gray-800 text-gray-400'
                        }`}
                >
                    🔔 Alerts ({alerts.length})
                </button>
                <button
                    onClick={() => setTab('rules')}
                    className={`px-4 py-2 rounded-lg font-medium transition-all ${tab === 'rules' ? 'bg-primary-600 text-white' : 'bg-gray-800 text-gray-400'
                        }`}
                >
                    📋 Rules ({rules.length})
                </button>
            </div>

            {/* Content */}
            {tab === 'alerts' ? (
                <>
                    {/* Filters */}
                    <div className="flex gap-2 flex-wrap">
                        {['all', 'firing', 'acknowledged', 'critical', 'warning'].map((f) => (
                            <button
                                key={f}
                                onClick={() => setFilter(f)}
                                className={`px-3 py-1.5 rounded-lg text-sm transition-all ${filter === f ? 'bg-primary-600 text-white' : 'bg-gray-800 text-gray-400'
                                    }`}
                            >
                                {f.charAt(0).toUpperCase() + f.slice(1)}
                            </button>
                        ))}
                    </div>

                    {/* Alert Grid */}
                    {filteredAlerts.length > 0 ? (
                        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                            {filteredAlerts.map((alert) => (
                                <AlertCard key={alert.id} alert={alert} onAction={handleAlertAction} />
                            ))}
                        </div>
                    ) : (
                        <div className="glass-card rounded-xl p-8 text-center">
                            <span className="text-5xl mb-4 block">✅</span>
                            <h3 className="text-xl font-semibold text-gray-100 mb-2">No alerts</h3>
                            <p className="text-gray-500">All systems operating normally</p>
                        </div>
                    )}
                </>
            ) : (
                /* Rules Grid */
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                    {rules.map((rule) => (
                        <RuleCard
                            key={rule.id}
                            rule={rule}
                            onToggle={handleRuleToggle}
                            onDelete={handleRuleDelete}
                        />
                    ))}
                </div>
            )}

            {/* Create Rule Modal */}
            {showCreateRule && (
                <CreateRuleModal
                    onClose={() => setShowCreateRule(false)}
                    onCreate={handleCreateRule}
                />
            )}
        </div>
    )
}
