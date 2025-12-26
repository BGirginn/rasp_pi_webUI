import { useState, useEffect } from 'react'
import { api } from '../services/api'
import { useAuth } from '../hooks/useAuth'

// Service card component
function ServiceCard({ resource, onAction }) {
    const { isOperator } = useAuth()
    const [loading, setLoading] = useState(false)

    const stateColors = {
        running: 'text-green-400',
        stopped: 'text-gray-400',
        failed: 'text-red-400',
        restarting: 'text-yellow-400',
    }

    const classColors = {
        CORE: 'bg-purple-500/20 text-purple-400 border-purple-500/30',
        SYSTEM: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
        APP: 'bg-green-500/20 text-green-400 border-green-500/30',
        DEVICE: 'bg-cyan-500/20 text-cyan-400 border-cyan-500/30',
    }

    const handleAction = async (action) => {
        setLoading(true)
        try {
            await onAction(resource.id, action)
        } finally {
            setLoading(false)
        }
    }

    // CORE = view only, SYSTEM = restart only, APP = full control
    const isCore = resource.resource_class === 'CORE'
    const isSystem = resource.resource_class === 'SYSTEM'
    const isDocker = resource.provider === 'docker'
    const canRestart = isOperator && !isCore
    const canStart = isOperator && !isCore && !isDocker
    const canStop = isOperator && resource.resource_class === 'APP'

    return (
        <div className="glass-card rounded-xl p-5 animate-slide-in">
            <div className="flex items-start justify-between mb-4">
                <div className="flex items-center gap-3">
                    <div className={`status-dot ${resource.state}`}></div>
                    <div>
                        <h3 className="font-semibold text-gray-100">{resource.name}</h3>
                        <p className="text-sm text-gray-500">{resource.provider} • {resource.type}</p>
                    </div>
                </div>
                <span className={`class-badge ${resource.resource_class?.toLowerCase()}`}>
                    {resource.resource_class}
                </span>
            </div>

            <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                    <span className={`text-sm font-medium ${stateColors[resource.state]}`}>
                        {resource.state.charAt(0).toUpperCase() + resource.state.slice(1)}
                    </span>
                    {resource.health_score && (
                        <span className="text-xs text-gray-500">
                            • Health: {resource.health_score}%
                        </span>
                    )}
                </div>

                <div className="flex gap-2">
                    {canRestart && resource.state === 'running' && (
                        <button
                            onClick={() => handleAction('restart')}
                            disabled={loading}
                            className="btn btn-secondary text-sm py-1 px-3"
                        >
                            {loading ? '...' : '🔄 Restart'}
                        </button>
                    )}
                    {canStart && resource.state === 'stopped' && (
                        <button
                            onClick={() => handleAction('start')}
                            disabled={loading}
                            className="btn btn-primary text-sm py-1 px-3"
                        >
                            {loading ? '...' : '▶️ Start'}
                        </button>
                    )}
                    {canStop && resource.state === 'running' && (
                        <button
                            onClick={() => handleAction('stop')}
                            disabled={loading}
                            className="btn btn-danger text-sm py-1 px-3"
                        >
                            {loading ? '...' : '⏹️ Stop'}
                        </button>
                    )}
                </div>
            </div>
        </div>
    )
}

// Filter tabs component
function FilterTabs({ filters, activeFilter, onChange }) {
    return (
        <div className="flex gap-2 flex-wrap">
            {filters.map((filter) => (
                <button
                    key={filter.value}
                    onClick={() => onChange(filter.value)}
                    className={`px-4 py-2 rounded-lg text-sm font-medium transition-all ${activeFilter === filter.value
                        ? 'bg-primary-600 text-white'
                        : 'bg-gray-800 text-gray-400 hover:bg-gray-700'
                        }`}
                >
                    {filter.label}
                    {filter.count !== undefined && (
                        <span className="ml-2 px-2 py-0.5 rounded-full bg-gray-700 text-xs">
                            {filter.count}
                        </span>
                    )}
                </button>
            ))}
        </div>
    )
}

export default function Services() {
    const [resources, setResources] = useState([])
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState(null)
    const [filter, setFilter] = useState('all')
    const [search, setSearch] = useState('')
    const [actionsMap, setActionsMap] = useState({})

    useEffect(() => {
        loadResources()
        loadActions()
    }, [])

    async function loadResources() {
        try {
            setLoading(true)
            const response = await api.get('/resources')
            setResources(response.data)
        } catch (err) {
            setError('Failed to load resources')
            console.error(err)
        } finally {
            setLoading(false)
        }
    }

    async function handleAction(resourceId, action) {
        try {
            const resource = resources.find((item) => item.id === resourceId)
            if (!resource) throw new Error('Resource not found')

            const actionId = mapResourceAction(resource, action)
            if (!actionId) {
                alert('Action not available in Action Registry')
                return
            }

            const actionMeta = actionsMap[actionId]
            const needsConfirm = actionMeta?.requires_confirmation
            const confirmed = needsConfirm ? window.confirm('Confirm this action?') : false

            const params = buildActionParams(resource, actionId)
            await api.post('/actions/execute', {
                action_id: actionId,
                params,
                confirm: confirmed,
            })
            // Reload after action
            await loadResources()
        } catch (err) {
            console.error('Action failed:', err)
            alert(`Action failed: ${err.message}`)
        }
    }

    async function loadActions() {
        try {
            const response = await api.get('/actions')
            const map = {}
            response.data.forEach((action) => {
                map[action.id] = action
            })
            setActionsMap(map)
        } catch (err) {
            console.error('Failed to load actions:', err)
        }
    }

    function normalizeServiceName(resource) {
        if (resource.id?.endsWith('.service')) return resource.id.replace('.service', '')
        if (resource.id?.startsWith('systemd-')) return resource.id.replace('systemd-', '')
        return resource.name
    }

    function mapResourceAction(resource, action) {
        if (resource.provider === 'systemd') {
            return `svc.${action}`
        }
        if (resource.provider === 'docker') {
            if (action === 'restart') return 'docker.restart_container'
            if (action === 'stop') return 'docker.stop_container'
            if (action === 'list') return 'docker.list'
        }
        return null
    }

    function buildActionParams(resource, actionId) {
        if (actionId.startsWith('svc.')) {
            return { service: normalizeServiceName(resource) }
        }
        if (actionId.startsWith('docker.')) {
            return { container_id: resource.id }
        }
        return {}
    }

    // Filter resources
    const filteredResources = resources.filter((r) => {
        if (filter !== 'all') {
            if (filter === 'docker' && r.provider !== 'docker') return false
            if (filter === 'systemd' && r.provider !== 'systemd') return false
            if (filter === 'running' && r.state !== 'running') return false
            if (filter === 'stopped' && r.state !== 'stopped') return false
        }
        if (search && !r.name.toLowerCase().includes(search.toLowerCase())) {
            return false
        }
        return true
    })

    // Calculate counts
    const counts = {
        all: resources.length,
        docker: resources.filter((r) => r.provider === 'docker').length,
        systemd: resources.filter((r) => r.provider === 'systemd').length,
        running: resources.filter((r) => r.state === 'running').length,
        stopped: resources.filter((r) => r.state === 'stopped').length,
    }

    const filters = [
        { value: 'all', label: 'All', count: counts.all },
        { value: 'docker', label: '🐳 Docker', count: counts.docker },
        { value: 'systemd', label: '⚙️ Systemd', count: counts.systemd },
        { value: 'running', label: '🟢 Running', count: counts.running },
        { value: 'stopped', label: '⚫ Stopped', count: counts.stopped },
    ]

    if (loading) {
        return (
            <div className="flex items-center justify-center h-64">
                <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-primary-500"></div>
            </div>
        )
    }

    return (
        <div className="space-y-6 animate-fade-in">
            {/* Header */}
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                <h2 className="text-2xl font-bold text-gray-100">Services</h2>
                <div className="flex gap-3">
                    <input
                        type="text"
                        value={search}
                        onChange={(e) => setSearch(e.target.value)}
                        placeholder="Search services..."
                        className="input w-64"
                    />
                    <button onClick={loadResources} className="btn btn-secondary">
                        🔄 Refresh
                    </button>
                </div>
            </div>

            {/* Filters */}
            <FilterTabs filters={filters} activeFilter={filter} onChange={setFilter} />

            {/* Error */}
            {error && (
                <div className="p-4 bg-red-500/20 border border-red-500/30 rounded-lg text-red-400">
                    {error}
                </div>
            )}

            {/* Grid */}
            {filteredResources.length > 0 ? (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                    {filteredResources.map((resource) => (
                        <ServiceCard
                            key={resource.id}
                            resource={resource}
                            onAction={handleAction}
                        />
                    ))}
                </div>
            ) : (
                <div className="glass-card rounded-xl p-8 text-center">
                    <span className="text-5xl mb-4 block">📦</span>
                    <h3 className="text-xl font-semibold text-gray-100 mb-2">
                        No services found
                    </h3>
                    <p className="text-gray-500">
                        {search
                            ? `No services matching "${search}"`
                            : 'No services discovered yet'}
                    </p>
                </div>
            )}
        </div>
    )
}
