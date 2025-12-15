import { useState, useEffect } from 'react'
import { api } from '../services/api'

// Format uptime
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

// Neon Metric Card
function MetricCard({ title, value, unit, icon, color = 'purple', subtitle }) {
    const colorConfig = {
        purple: { gradient: 'from-purple-600 to-pink-600', glow: 'shadow-[0_0_30px_rgba(168,85,247,0.3)]' },
        green: { gradient: 'from-emerald-500 to-teal-500', glow: 'shadow-[0_0_30px_rgba(16,185,129,0.3)]' },
        yellow: { gradient: 'from-amber-500 to-orange-500', glow: 'shadow-[0_0_30px_rgba(245,158,11,0.3)]' },
        red: { gradient: 'from-red-500 to-rose-500', glow: 'shadow-[0_0_30px_rgba(239,68,68,0.3)]' },
    }
    const cfg = colorConfig[color]

    return (
        <div className="metric-card group">
            <div className="flex items-start justify-between mb-5">
                <div className={`w-12 h-12 rounded-xl bg-gradient-to-br ${cfg.gradient} flex items-center justify-center ${cfg.glow} group-hover:scale-105 transition-transform`}>
                    <span className="text-xl">{icon}</span>
                </div>
                {subtitle && (
                    <span className="text-[10px] font-medium text-zinc-500 bg-white/[0.03] px-2 py-1 rounded-md uppercase tracking-wide">
                        {subtitle}
                    </span>
                )}
            </div>

            <p className="text-xs font-medium text-zinc-500 uppercase tracking-wider mb-1">{title}</p>
            <p className="text-3xl font-bold text-white">
                {value}
                {unit && <span className="text-lg font-normal text-zinc-500 ml-1">{unit}</span>}
            </p>
        </div>
    )
}

// Alert Card
function AlertCard({ severity, message, time }) {
    const config = {
        critical: { bg: 'bg-red-500/5', border: 'border-l-red-500', icon: '●', text: 'text-red-400' },
        warning: { bg: 'bg-amber-500/5', border: 'border-l-amber-500', icon: '●', text: 'text-amber-400' },
        info: { bg: 'bg-blue-500/5', border: 'border-l-blue-500', icon: '●', text: 'text-blue-400' },
    }
    const c = config[severity] || config.info

    return (
        <div className={`border-l-2 ${c.border} ${c.bg} rounded-r-xl p-4 flex items-center gap-3`}>
            <span className={`text-sm ${c.text}`}>{c.icon}</span>
            <div className="flex-1 min-w-0">
                <p className={`text-sm ${c.text} font-medium`}>{message}</p>
                <p className="text-xs text-zinc-600 mt-0.5">{time}</p>
            </div>
        </div>
    )
}

// Resource Card
function ResourceCard({ name, type, state, provider }) {
    const stateConfig = {
        running: { dot: 'running', text: 'text-emerald-400', label: 'RUNNING' },
        stopped: { dot: 'stopped', text: 'text-zinc-500', label: 'STOPPED' },
        failed: { dot: 'failed', text: 'text-red-400', label: 'FAILED' },
    }
    const cfg = stateConfig[state] || stateConfig.stopped

    return (
        <div className="flex items-center gap-4 p-3 rounded-xl bg-white/[0.02] hover:bg-white/[0.04] transition-colors border border-white/[0.02] hover:border-purple-500/10">
            <div className={`status-dot ${cfg.dot}`}></div>
            <div className="flex-1 min-w-0">
                <p className="font-medium text-white truncate">{name}</p>
                <p className="text-xs text-zinc-600">{provider} • {type}</p>
            </div>
            <span className={`text-[10px] font-semibold ${cfg.text} tracking-wider`}>
                {cfg.label}
            </span>
        </div>
    )
}

export default function Dashboard() {
    const [loading, setLoading] = useState(true)
    const [stats, setStats] = useState({
        cpu: 0, memory: 0, memUsedGb: 0, memTotalGb: 0,
        disk: 0, diskUsedGb: 0, diskTotalGb: 0,
        temp: 0, uptime: 0, hostname: '...', os: '...', machine: '...',
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
                <div className="w-10 h-10 border-2 border-purple-500/30 border-t-purple-500 rounded-full animate-spin"></div>
            </div>
        )
    }

    return (
        <div className="space-y-8 animate-fade-in">
            {/* Header */}
            <div>
                <h1 className="text-3xl font-bold text-white mb-1">Dashboard</h1>
                <p className="text-zinc-500 text-sm">Welcome to <span className="text-purple-400">{stats.hostname}</span></p>
            </div>

            {/* Metrics */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-5">
                <MetricCard
                    title="CPU Usage"
                    value={stats.cpu}
                    unit="%"
                    icon="⚡"
                    color={getColor(stats.cpu, 60, 80)}
                    subtitle={stats.machine}
                />
                <MetricCard
                    title="Memory"
                    value={stats.memUsedGb}
                    unit={`/ ${stats.memTotalGb} GB`}
                    icon="◈"
                    color={getColor(stats.memory, 60, 80)}
                    subtitle={`${stats.memory}%`}
                />
                <MetricCard
                    title="Disk"
                    value={stats.diskUsedGb}
                    unit={`/ ${stats.diskTotalGb} GB`}
                    icon="◆"
                    color={getColor(stats.disk, 70, 85)}
                    subtitle={`${stats.disk}%`}
                />
                <MetricCard
                    title="Temperature"
                    value={stats.temp || 'N/A'}
                    unit={stats.temp ? '°C' : ''}
                    icon="◎"
                    color={getColor(stats.temp, 60, 70)}
                    subtitle={formatUptime(stats.uptime)}
                />
            </div>

            {/* Two columns */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                {/* Alerts */}
                <div className="glass-card p-6">
                    <div className="flex items-center justify-between mb-5">
                        <h3 className="text-base font-semibold text-white">Active Alerts</h3>
                        <span className="text-[10px] font-medium text-zinc-500 bg-white/[0.03] px-2 py-1 rounded-md">
                            {alerts.length} ACTIVE
                        </span>
                    </div>
                    {alerts.length > 0 ? (
                        <div className="space-y-3">
                            {alerts.map((alert, i) => (
                                <AlertCard key={i} severity={alert.severity || 'info'} message={alert.message || 'Alert'} time={alert.fired_at || 'Just now'} />
                            ))}
                        </div>
                    ) : (
                        <div className="text-center py-12">
                            <span className="text-3xl mb-3 block opacity-50">✓</span>
                            <p className="text-zinc-500 text-sm">All systems operational</p>
                        </div>
                    )}
                </div>

                {/* Services */}
                <div className="glass-card p-6">
                    <div className="flex items-center justify-between mb-5">
                        <h3 className="text-base font-semibold text-white">Services</h3>
                        <span className="text-[10px] font-medium text-emerald-400 bg-emerald-500/10 px-2 py-1 rounded-md">
                            {resources.filter(r => r.state === 'running').length} RUNNING
                        </span>
                    </div>
                    {resources.length > 0 ? (
                        <div className="space-y-2">
                            {resources.map((resource) => (
                                <ResourceCard key={resource.id} name={resource.name} type={resource.type} state={resource.state} provider={resource.provider} />
                            ))}
                        </div>
                    ) : (
                        <div className="text-center py-12">
                            <span className="text-3xl mb-3 block opacity-50">◇</span>
                            <p className="text-zinc-500 text-sm">No services discovered</p>
                        </div>
                    )}
                </div>
            </div>

            {/* System Info */}
            <div className="glass-card p-6">
                <h3 className="text-base font-semibold text-white mb-5">System Info</h3>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-6">
                    <div>
                        <p className="text-[10px] text-zinc-600 uppercase tracking-wider mb-1">Hostname</p>
                        <p className="text-white font-mono text-sm">{stats.hostname}</p>
                    </div>
                    <div>
                        <p className="text-[10px] text-zinc-600 uppercase tracking-wider mb-1">OS</p>
                        <p className="text-white text-sm">{stats.os}</p>
                    </div>
                    <div>
                        <p className="text-[10px] text-zinc-600 uppercase tracking-wider mb-1">Uptime</p>
                        <p className="text-white font-mono text-sm">{formatUptime(stats.uptime)}</p>
                    </div>
                    <div>
                        <p className="text-[10px] text-zinc-600 uppercase tracking-wider mb-1">Architecture</p>
                        <p className="text-white font-mono text-sm">{stats.machine}</p>
                    </div>
                </div>
            </div>
        </div>
    )
}
