import { useState, useEffect } from 'react'
import { api } from '../services/api'

// Format uptime from seconds to human readable
function formatUptime(seconds) {
    if (!seconds || seconds <= 0) return 'N/A'

    const days = Math.floor(seconds / 86400)
    const hours = Math.floor((seconds % 86400) / 3600)
    const minutes = Math.floor((seconds % 3600) / 60)

    const parts = []
    if (days > 0) parts.push(`${days}d`)
    if (hours > 0) parts.push(`${hours}h`)
    if (minutes > 0 && days === 0) parts.push(`${minutes}m`)

    return parts.join(' ') || '< 1m'
}

// Metric card with neon border
function MetricCard({ title, value, unit, icon, color = 'purple', subtitle }) {
    const colorMap = {
        purple: 'from-primary-500 to-primary-700',
        green: 'from-green-500 to-green-700',
        yellow: 'from-yellow-500 to-yellow-700',
        red: 'from-red-500 to-red-700',
        blue: 'from-blue-500 to-blue-700',
    }

    const glowMap = {
        purple: 'shadow-neon',
        green: 'shadow-neon-success',
        yellow: 'shadow-[0_0_20px_rgba(245,158,11,0.3)]',
        red: 'shadow-neon-danger',
        blue: 'shadow-[0_0_20px_rgba(59,130,246,0.3)]',
    }

    return (
        <div className="metric-card group">
            {/* Gradient top border */}
            <div className={`absolute top-0 left-0 right-0 h-1 bg-gradient-to-r ${colorMap[color]} opacity-60 group-hover:opacity-100 transition-opacity`}></div>

            <div className="flex items-start justify-between mb-4">
                <div className={`w-12 h-12 rounded-xl bg-gradient-to-br ${colorMap[color]} flex items-center justify-center ${glowMap[color]}`}>
                    <span className="text-xl">{icon}</span>
                </div>
                {subtitle && (
                    <span className="text-xs text-gray-500 bg-dark-100 px-2 py-1 rounded-lg">
                        {subtitle}
                    </span>
                )}
            </div>

            <p className="text-sm text-gray-400 mb-1">{title}</p>
            <p className="text-3xl font-bold text-white">
                {value}
                {unit && <span className="text-lg font-normal text-gray-400 ml-1">{unit}</span>}
            </p>
        </div>
    )
}

// Alert card component
function AlertCard({ severity, message, time }) {
    const severityConfig = {
        critical: {
            bg: 'bg-red-500/10',
            border: 'border-l-red-500',
            icon: '🔴',
            text: 'text-red-400'
        },
        warning: {
            bg: 'bg-yellow-500/10',
            border: 'border-l-yellow-500',
            icon: '🟡',
            text: 'text-yellow-400'
        },
        info: {
            bg: 'bg-blue-500/10',
            border: 'border-l-blue-500',
            icon: '🔵',
            text: 'text-blue-400'
        },
    }

    const config = severityConfig[severity] || severityConfig.info

    return (
        <div className={`border-l-4 ${config.border} ${config.bg} rounded-r-xl p-4 flex items-center gap-3 backdrop-blur-sm`}>
            <span className="text-lg">{config.icon}</span>
            <div className="flex-1 min-w-0">
                <p className={`text-sm ${config.text} font-medium`}>{message}</p>
                <p className="text-xs text-gray-500 mt-0.5">{time}</p>
            </div>
        </div>
    )
}

// Resource card component
function ResourceCard({ name, type, state, healthScore, provider }) {
    const stateConfig = {
        running: { dot: 'running', text: 'text-green-400' },
        stopped: { dot: 'stopped', text: 'text-gray-400' },
        failed: { dot: 'failed', text: 'text-red-400' },
    }

    const config = stateConfig[state] || stateConfig.stopped

    return (
        <div className="flex items-center gap-4 p-3 rounded-xl bg-dark-100/50 hover:bg-dark-50/50 transition-colors border border-primary-500/5 hover:border-primary-500/20">
            <div className={`status-dot ${config.dot}`}></div>
            <div className="flex-1 min-w-0">
                <p className="font-medium text-white truncate">{name}</p>
                <p className="text-xs text-gray-500">{provider} • {type}</p>
            </div>
            <span className={`text-xs font-mono ${config.text} bg-dark-200 px-2 py-1 rounded`}>
                {state}
            </span>
        </div>
    )
}

export default function Dashboard() {
    const [loading, setLoading] = useState(true)
    const [stats, setStats] = useState({
        cpu: 0,
        memory: 0,
        memUsedGb: 0,
        memTotalGb: 0,
        disk: 0,
        diskUsedGb: 0,
        diskTotalGb: 0,
        temp: 0,
        uptime: 0,
        hostname: 'Loading...',
        os: 'Loading...',
        machine: 'Loading...',
    })
    const [resources, setResources] = useState([])
    const [alerts, setAlerts] = useState([])

    useEffect(() => {
        loadDashboardData()
        const interval = setInterval(loadDashboardData, 5000)
        return () => clearInterval(interval)
    }, [])

    async function loadDashboardData() {
        try {
            const telemetryRes = await api.get('/telemetry/current')
            const metrics = telemetryRes.data?.metrics || {}
            const systemInfo = telemetryRes.data?.system || {}

            setStats({
                cpu: Math.round(metrics['host.cpu.pct_total'] || 0),
                memory: Math.round(metrics['host.mem.pct'] || 0),
                memUsedGb: ((metrics['host.mem.used_mb'] || 0) / 1024).toFixed(1),
                memTotalGb: ((metrics['host.mem.total_mb'] || 0) / 1024).toFixed(1),
                disk: Math.round(metrics['disk._root.used_pct'] || 0),
                diskUsedGb: (metrics['disk._root.used_gb'] || 0).toFixed(1),
                diskTotalGb: (metrics['disk._root.total_gb'] || 0).toFixed(1),
                temp: Math.round(metrics['host.temp.cpu_c'] || 0),
                uptime: metrics['host.uptime.seconds'] || 0,
                hostname: systemInfo.hostname || 'Unknown',
                os: systemInfo.os || 'Unknown',
                machine: systemInfo.machine || 'Unknown',
            })

            const resourcesRes = await api.get('/resources')
            setResources(resourcesRes.data.slice(0, 5))

            const alertsRes = await api.get('/alerts')
            setAlerts(alertsRes.data.slice(0, 3))
        } catch (err) {
            console.error('Failed to load dashboard data:', err)
        } finally {
            setLoading(false)
        }
    }

    const getColor = (value, warn, crit) => {
        if (value >= crit) return 'red'
        if (value >= warn) return 'yellow'
        return 'green'
    }

    if (loading) {
        return (
            <div className="flex items-center justify-center h-64">
                <div className="w-12 h-12 border-4 border-primary-500/30 border-t-primary-500 rounded-full animate-spin"></div>
            </div>
        )
    }

    return (
        <div className="space-y-6 animate-fade-in">
            {/* Welcome header */}
            <div className="mb-8">
                <h1 className="text-3xl font-bold gradient-text">Dashboard</h1>
                <p className="text-gray-500 mt-1">Welcome to {stats.hostname}</p>
            </div>

            {/* Metrics grid */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-5">
                <MetricCard
                    title="CPU Usage"
                    value={stats.cpu}
                    unit="%"
                    icon="⚡"
                    color={getColor(stats.cpu, 60, 80)}
                    subtitle={`${stats.machine}`}
                />
                <MetricCard
                    title="Memory"
                    value={stats.memUsedGb}
                    unit={`/ ${stats.memTotalGb} GB`}
                    icon="💾"
                    color={getColor(stats.memory, 60, 80)}
                    subtitle={`${stats.memory}%`}
                />
                <MetricCard
                    title="Disk"
                    value={stats.diskUsedGb}
                    unit={`/ ${stats.diskTotalGb} GB`}
                    icon="💿"
                    color={getColor(stats.disk, 70, 85)}
                    subtitle={`${stats.disk}%`}
                />
                <MetricCard
                    title="Temperature"
                    value={stats.temp || 'N/A'}
                    unit={stats.temp ? '°C' : ''}
                    icon="🌡️"
                    color={getColor(stats.temp, 60, 70)}
                    subtitle={formatUptime(stats.uptime)}
                />
            </div>

            {/* Two column layout */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                {/* Active Alerts */}
                <div className="glass-card rounded-2xl p-6">
                    <div className="flex items-center justify-between mb-5">
                        <h3 className="text-lg font-semibold text-white">Active Alerts</h3>
                        <span className="text-xs text-gray-500 bg-dark-100 px-3 py-1 rounded-full">
                            {alerts.length} active
                        </span>
                    </div>
                    {alerts.length > 0 ? (
                        <div className="space-y-3">
                            {alerts.map((alert, i) => (
                                <AlertCard
                                    key={i}
                                    severity={alert.severity || 'info'}
                                    message={alert.message || 'Alert message'}
                                    time={alert.fired_at || 'Just now'}
                                />
                            ))}
                        </div>
                    ) : (
                        <div className="text-center py-10">
                            <span className="text-4xl mb-3 block">✅</span>
                            <p className="text-gray-400">All systems operational</p>
                        </div>
                    )}
                </div>

                {/* Top Resources */}
                <div className="glass-card rounded-2xl p-6">
                    <div className="flex items-center justify-between mb-5">
                        <h3 className="text-lg font-semibold text-white">Services</h3>
                        <span className="text-xs text-gray-500 bg-dark-100 px-3 py-1 rounded-full">
                            {resources.filter(r => r.state === 'running').length} running
                        </span>
                    </div>
                    {resources.length > 0 ? (
                        <div className="space-y-2">
                            {resources.map((resource) => (
                                <ResourceCard
                                    key={resource.id}
                                    name={resource.name}
                                    type={resource.type}
                                    state={resource.state}
                                    healthScore={resource.health_score || 95}
                                    provider={resource.provider}
                                />
                            ))}
                        </div>
                    ) : (
                        <div className="text-center py-10">
                            <span className="text-4xl mb-3 block">📦</span>
                            <p className="text-gray-400">No services discovered</p>
                        </div>
                    )}
                </div>
            </div>

            {/* System Info */}
            <div className="glass-card rounded-2xl p-6">
                <h3 className="text-lg font-semibold text-white mb-5">System Info</h3>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-6">
                    <div>
                        <p className="text-xs text-gray-500 uppercase tracking-wider mb-1">Hostname</p>
                        <p className="text-white font-mono">{stats.hostname}</p>
                    </div>
                    <div>
                        <p className="text-xs text-gray-500 uppercase tracking-wider mb-1">Operating System</p>
                        <p className="text-white">{stats.os}</p>
                    </div>
                    <div>
                        <p className="text-xs text-gray-500 uppercase tracking-wider mb-1">Uptime</p>
                        <p className="text-white font-mono">{formatUptime(stats.uptime)}</p>
                    </div>
                    <div>
                        <p className="text-xs text-gray-500 uppercase tracking-wider mb-1">Architecture</p>
                        <p className="text-white font-mono">{stats.machine}</p>
                    </div>
                </div>
            </div>
        </div>
    )
}
