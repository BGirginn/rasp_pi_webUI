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
// Stat card component
function StatCard({ title, value, unit, icon, trend, color = 'primary' }) {
    const colorClasses = {
        primary: 'from-primary-500/20 to-primary-600/10 border-primary-500/30',
        success: 'from-green-500/20 to-green-600/10 border-green-500/30',
        warning: 'from-yellow-500/20 to-yellow-600/10 border-yellow-500/30',
        danger: 'from-red-500/20 to-red-600/10 border-red-500/30',
    }

    return (
        <div className={`glass-card rounded-xl p-5 bg-gradient-to-br ${colorClasses[color]} border`}>
            <div className="flex items-start justify-between mb-3">
                <span className="text-2xl">{icon}</span>
                {trend && (
                    <span className={`text-xs ${trend > 0 ? 'text-green-400' : 'text-red-400'}`}>
                        {trend > 0 ? '↑' : '↓'} {Math.abs(trend)}%
                    </span>
                )}
            </div>
            <p className="text-gray-400 text-sm mb-1">{title}</p>
            <p className="text-2xl font-bold text-gray-100">
                {value}
                {unit && <span className="text-lg font-normal text-gray-400 ml-1">{unit}</span>}
            </p>
        </div>
    )
}

// Alert card component
function AlertCard({ severity, message, time }) {
    const severityStyles = {
        critical: 'border-l-red-500 bg-red-500/10',
        warning: 'border-l-yellow-500 bg-yellow-500/10',
        info: 'border-l-blue-500 bg-blue-500/10',
    }

    const severityIcons = {
        critical: '🔴',
        warning: '🟡',
        info: '🔵',
    }

    return (
        <div className={`border-l-4 ${severityStyles[severity]} rounded-r-lg p-3 flex items-center gap-3`}>
            <span className="text-lg">{severityIcons[severity]}</span>
            <div className="flex-1">
                <p className="text-sm text-gray-100">{message}</p>
                <p className="text-xs text-gray-500">{time}</p>
            </div>
        </div>
    )
}

// Resource card component
function ResourceCard({ name, type, state, healthScore, provider }) {
    const stateStyles = {
        running: 'running',
        stopped: 'stopped',
        failed: 'failed',
    }

    const healthBadge = {
        healthy: healthScore >= 90,
        degraded: healthScore >= 70 && healthScore < 90,
        warning: healthScore >= 50 && healthScore < 70,
        critical: healthScore < 50,
    }

    const healthClass = Object.keys(healthBadge).find((k) => healthBadge[k])

    return (
        <div className="glass-card rounded-lg p-4 flex items-center gap-4">
            <div className={`status-dot ${stateStyles[state]}`}></div>
            <div className="flex-1 min-w-0">
                <p className="font-medium text-gray-100 truncate">{name}</p>
                <p className="text-xs text-gray-500">{provider} • {type}</p>
            </div>
            <span className={`health-badge ${healthClass}`}>
                {healthScore}
            </span>
        </div>
    )
}

export default function Dashboard() {
    const [loading, setLoading] = useState(true)
    const [stats, setStats] = useState({
        cpu: 0,
        memory: 0,
        disk: 0,
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

        // Refresh every 5 seconds
        const interval = setInterval(loadDashboardData, 5000)
        return () => clearInterval(interval)
    }, [])

    async function loadDashboardData() {
        try {
            // Load telemetry (real system metrics)
            const telemetryRes = await api.get('/telemetry/current')
            const metrics = telemetryRes.data?.metrics || {}
            const systemInfo = telemetryRes.data?.system || {}

            setStats({
                cpu: Math.round(metrics['host.cpu.pct_total'] || 0),
                memory: Math.round(metrics['host.mem.pct'] || 0),
                disk: Math.round(metrics['disk._root.used_pct'] || 0),
                temp: Math.round(metrics['host.temp.cpu_c'] || 0),
                uptime: metrics['host.uptime.seconds'] || 0,
                hostname: systemInfo.hostname || 'Unknown',
                os: systemInfo.os || 'Unknown',
                machine: systemInfo.machine || 'Unknown',
            })

            // Load resources
            const resourcesRes = await api.get('/resources')
            setResources(resourcesRes.data.slice(0, 5)) // Top 5

            // Load alerts
            const alertsRes = await api.get('/alerts')
            setAlerts(alertsRes.data.slice(0, 3)) // Top 3
        } catch (err) {
            console.error('Failed to load dashboard data:', err)
        } finally {
            setLoading(false)
        }
    }

    if (loading) {
        return (
            <div className="flex items-center justify-center h-64">
                <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-primary-500"></div>
            </div>
        )
    }

    return (
        <div className="space-y-6 animate-fade-in">
            {/* Stats grid */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                <StatCard
                    title="CPU Usage"
                    value={stats.cpu}
                    unit="%"
                    icon="🔲"
                    color={stats.cpu > 80 ? 'danger' : stats.cpu > 60 ? 'warning' : 'success'}
                />
                <StatCard
                    title="Memory"
                    value={stats.memory}
                    unit="%"
                    icon="💾"
                    color={stats.memory > 80 ? 'danger' : stats.memory > 60 ? 'warning' : 'success'}
                />
                <StatCard
                    title="Disk"
                    value={stats.disk}
                    unit="%"
                    icon="💽"
                    color={stats.disk > 85 ? 'danger' : stats.disk > 70 ? 'warning' : 'primary'}
                />
                <StatCard
                    title="Temperature"
                    value={stats.temp}
                    unit="°C"
                    icon="🌡️"
                    color={stats.temp > 70 ? 'danger' : stats.temp > 60 ? 'warning' : 'success'}
                />
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                {/* Active Alerts */}
                <div className="glass-card rounded-xl p-5">
                    <h3 className="text-lg font-semibold text-gray-100 mb-4">Active Alerts</h3>
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
                        <div className="text-center py-8 text-gray-500">
                            <span className="text-3xl mb-2 block">✅</span>
                            <p>No active alerts</p>
                        </div>
                    )}
                </div>

                {/* Top Resources */}
                <div className="glass-card rounded-xl p-5">
                    <h3 className="text-lg font-semibold text-gray-100 mb-4">Top Resources</h3>
                    {resources.length > 0 ? (
                        <div className="space-y-3">
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
                        <div className="text-center py-8 text-gray-500">
                            <span className="text-3xl mb-2 block">📦</span>
                            <p>No resources discovered yet</p>
                        </div>
                    )}
                </div>
            </div>

            {/* System Info */}
            <div className="glass-card rounded-xl p-5">
                <h3 className="text-lg font-semibold text-gray-100 mb-4">System Info</h3>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                    <div>
                        <p className="text-gray-500">Hostname</p>
                        <p className="text-gray-100">{stats.hostname}</p>
                    </div>
                    <div>
                        <p className="text-gray-500">OS</p>
                        <p className="text-gray-100">{stats.os}</p>
                    </div>
                    <div>
                        <p className="text-gray-500">Uptime</p>
                        <p className="text-gray-100">{formatUptime(stats.uptime)}</p>
                    </div>
                    <div>
                        <p className="text-gray-500">Architecture</p>
                        <p className="text-gray-100">{stats.machine}</p>
                    </div>
                </div>
            </div>
        </div>
    )
}
