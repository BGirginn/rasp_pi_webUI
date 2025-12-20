import { useState, useEffect, useMemo } from 'react'
import { api } from '../services/api'
import {
    LineChart,
    Line,
    AreaChart,
    Area,
    XAxis,
    YAxis,
    CartesianGrid,
    Tooltip,
    ResponsiveContainer,
} from 'recharts'
import { format } from 'date-fns'

// Metric card with sparkline
function MetricCard({ title, value, unit, data, color, icon }) {
    return (
        <div className="glass-card rounded-xl p-4">
            <div className="flex items-center justify-between mb-2">
                <span className="text-2xl">{icon}</span>
                <span className="text-2xl font-bold text-gray-100">
                    {value?.toFixed(1) || '--'}
                    <span className="text-lg font-normal text-gray-400 ml-1">{unit}</span>
                </span>
            </div>
            <p className="text-sm text-gray-500 mb-2">{title}</p>
            {data && data.length > 0 && (
                <div className="h-12">
                    <ResponsiveContainer width="100%" height="100%">
                        <AreaChart data={data}>
                            <Area
                                type="monotone"
                                dataKey="value"
                                stroke={color}
                                fill={`${color}40`}
                                strokeWidth={2}
                            />
                        </AreaChart>
                    </ResponsiveContainer>
                </div>
            )}
        </div>
    )
}

// Time range selector
function TimeRangeSelector({ value, onChange }) {
    const ranges = [
        { value: '1h', label: '1 Hour' },
        { value: '6h', label: '6 Hours' },
        { value: '24h', label: '24 Hours' },
        { value: '7d', label: '7 Days' },
    ]

    return (
        <div className="flex gap-2">
            {ranges.map((range) => (
                <button
                    key={range.value}
                    onClick={() => onChange(range.value)}
                    className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-all ${value === range.value
                            ? 'bg-primary-600 text-white'
                            : 'bg-gray-800 text-gray-400 hover:bg-gray-700'
                        }`}
                >
                    {range.label}
                </button>
            ))}
        </div>
    )
}

// Main chart component
function TelemetryChart({ data, metrics, timeRange }) {
    const colors = ['#38bdf8', '#22c55e', '#f59e0b', '#ef4444', '#a855f7']

    // Format timestamp for x-axis
    const formatTime = (ts) => {
        const date = new Date(ts * 1000)
        if (timeRange === '7d') {
            return format(date, 'MMM d')
        } else if (timeRange === '24h' || timeRange === '6h') {
            return format(date, 'HH:mm')
        }
        return format(date, 'HH:mm:ss')
    }

    return (
        <div className="glass-card rounded-xl p-5">
            <h3 className="text-lg font-semibold text-gray-100 mb-4">System Metrics</h3>

            <div className="h-64">
                <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={data}>
                        <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
                        <XAxis
                            dataKey="ts"
                            tickFormatter={formatTime}
                            stroke="#6b7280"
                            fontSize={12}
                        />
                        <YAxis stroke="#6b7280" fontSize={12} />
                        <Tooltip
                            contentStyle={{
                                backgroundColor: '#1f2937',
                                border: '1px solid #374151',
                                borderRadius: '8px',
                            }}
                            labelFormatter={(ts) => new Date(ts * 1000).toLocaleString()}
                        />
                        {metrics.map((metric, i) => (
                            <Line
                                key={metric}
                                type="monotone"
                                dataKey={metric}
                                stroke={colors[i % colors.length]}
                                strokeWidth={2}
                                dot={false}
                                name={metric.split('.').pop()}
                            />
                        ))}
                    </LineChart>
                </ResponsiveContainer>
            </div>

            <div className="flex flex-wrap gap-4 mt-4">
                {metrics.map((metric, i) => (
                    <div key={metric} className="flex items-center gap-2">
                        <div
                            className="w-3 h-3 rounded-full"
                            style={{ backgroundColor: colors[i % colors.length] }}
                        />
                        <span className="text-sm text-gray-400">
                            {metric.split('.').pop()}
                        </span>
                    </div>
                ))}
            </div>
        </div>
    )
}

export default function Telemetry() {
    const [dashboard, setDashboard] = useState(null)
    const [chartData, setChartData] = useState([])
    const [availableMetrics, setAvailableMetrics] = useState([])
    const [selectedMetrics, setSelectedMetrics] = useState(['cpu_pct', 'memory_pct'])
    const [timeRange, setTimeRange] = useState('1h')
    const [loading, setLoading] = useState(true)
    const [live, setLive] = useState(true)

    // Load dashboard data
    useEffect(() => {
        loadDashboard()

        let interval
        if (live) {
            interval = setInterval(loadDashboard, 5000)
        }
        return () => clearInterval(interval)
    }, [live])

    // Load chart data when time range changes
    useEffect(() => {
        loadChartData()
    }, [timeRange])

    async function loadDashboard() {
        try {
            const response = await api.get('/telemetry/dashboard')
            setDashboard(response.data)
        } catch (err) {
            console.error('Failed to load dashboard:', err)
        } finally {
            setLoading(false)
        }
    }

    async function loadChartData() {
        try {
            // Calculate time range
            const now = Math.floor(Date.now() / 1000)
            const hours = {
                '1h': 1,
                '6h': 6,
                '24h': 24,
                '7d': 168,
            }[timeRange]
            const start = now - hours * 3600

            // Query metrics
            const metrics = 'host.cpu.pct_total,host.mem.pct'
            const response = await api.get(`/telemetry/metrics?metrics=${metrics}&start=${start}&end=${now}`)

            // Transform data for chart
            const dataMap = {}
            response.data.forEach((metric) => {
                metric.points.forEach((point) => {
                    if (!dataMap[point.ts]) {
                        dataMap[point.ts] = { ts: point.ts }
                    }
                    const shortName = metric.metric.split('.').pop()
                    dataMap[point.ts][shortName] = point.value
                })
            })

            setChartData(Object.values(dataMap).sort((a, b) => a.ts - b.ts))
        } catch (err) {
            console.error('Failed to load chart data:', err)
        }
    }

    // Generate mock sparkline data
    const generateSparkline = (base, variance) => {
        return Array.from({ length: 20 }, (_, i) => ({
            value: base + (Math.random() - 0.5) * variance,
        }))
    }

    if (loading) {
        return (
            <div className="flex items-center justify-center h-64">
                <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-primary-500"></div>
            </div>
        )
    }

    const system = dashboard?.system || {}

    return (
        <div className="space-y-6 animate-fade-in">
            {/* Header */}
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                <h2 className="text-2xl font-bold text-gray-100">Telemetry</h2>
                <div className="flex items-center gap-4">
                    <button
                        onClick={() => setLive(!live)}
                        className={`px-4 py-2 rounded-lg text-sm font-medium transition-all flex items-center gap-2 ${live
                                ? 'bg-green-500/20 text-green-400 border border-green-500/30'
                                : 'bg-gray-800 text-gray-400'
                            }`}
                    >
                        <span className={`w-2 h-2 rounded-full ${live ? 'bg-green-400 animate-pulse' : 'bg-gray-600'}`} />
                        {live ? 'Live' : 'Paused'}
                    </button>
                    <TimeRangeSelector value={timeRange} onChange={setTimeRange} />
                </div>
            </div>

            {/* Metric Cards */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <MetricCard
                    title="CPU Usage"
                    value={system.cpu_pct}
                    unit="%"
                    icon="🔲"
                    color="#38bdf8"
                    data={generateSparkline(system.cpu_pct || 35, 15)}
                />
                <MetricCard
                    title="Memory"
                    value={system.memory_pct}
                    unit="%"
                    icon="💾"
                    color="#22c55e"
                    data={generateSparkline(system.memory_pct || 60, 10)}
                />
                <MetricCard
                    title="Disk Usage"
                    value={system.disk_pct}
                    unit="%"
                    icon="💽"
                    color="#f59e0b"
                    data={generateSparkline(system.disk_pct || 42, 5)}
                />
                <MetricCard
                    title="Temperature"
                    value={system.temperature_c}
                    unit="°C"
                    icon="🌡️"
                    color="#ef4444"
                    data={generateSparkline(system.temperature_c || 48, 8)}
                />
            </div>

            {/* Main Chart */}
            <TelemetryChart
                data={chartData}
                metrics={['pct_total', 'pct']}
                timeRange={timeRange}
            />

            {/* Additional Stats */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                {/* Load Average */}
                <div className="glass-card rounded-xl p-5">
                    <h3 className="text-lg font-semibold text-gray-100 mb-4">Load Average</h3>
                    <div className="grid grid-cols-3 gap-4 text-center">
                        <div>
                            <p className="text-2xl font-bold text-gray-100">
                                {system.load_1m?.toFixed(2) || '--'}
                            </p>
                            <p className="text-xs text-gray-500">1 min</p>
                        </div>
                        <div>
                            <p className="text-2xl font-bold text-gray-100">
                                {system.load_5m?.toFixed(2) || '--'}
                            </p>
                            <p className="text-xs text-gray-500">5 min</p>
                        </div>
                        <div>
                            <p className="text-2xl font-bold text-gray-100">
                                {system.load_15m?.toFixed(2) || '--'}
                            </p>
                            <p className="text-xs text-gray-500">15 min</p>
                        </div>
                    </div>
                </div>

                {/* Network I/O */}
                <div className="glass-card rounded-xl p-5">
                    <h3 className="text-lg font-semibold text-gray-100 mb-4">Network I/O</h3>
                    <div className="grid grid-cols-2 gap-4">
                        <div>
                            <p className="text-sm text-gray-400">↓ Received</p>
                            <p className="text-xl font-bold text-green-400">
                                {((system.network_rx_bytes || 0) / 1024 / 1024 / 1024).toFixed(2)} GB
                            </p>
                        </div>
                        <div>
                            <p className="text-sm text-gray-400">↑ Transmitted</p>
                            <p className="text-xl font-bold text-blue-400">
                                {((system.network_tx_bytes || 0) / 1024 / 1024 / 1024).toFixed(2)} GB
                            </p>
                        </div>
                    </div>
                </div>

                {/* Memory Details */}
                <div className="glass-card rounded-xl p-5">
                    <h3 className="text-lg font-semibold text-gray-100 mb-4">Memory</h3>
                    <div className="mb-2 flex justify-between text-sm">
                        <span className="text-gray-400">Used</span>
                        <span className="text-gray-100">
                            {(system.memory_used_mb / 1024).toFixed(1)} GB / {(system.memory_total_mb / 1024).toFixed(1)} GB
                        </span>
                    </div>
                    <div className="h-3 bg-gray-700 rounded-full overflow-hidden">
                        <div
                            className="h-full bg-gradient-to-r from-primary-500 to-primary-600 rounded-full transition-all"
                            style={{ width: `${system.memory_pct || 0}%` }}
                        />
                    </div>
                </div>
            </div>
        </div>
    )
}
